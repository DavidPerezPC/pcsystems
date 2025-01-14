from datetime import date
from odoo import models, fields, api

class AccountMoveWizard(models.TransientModel):
    """Deleted Inverted Wizard"""
    _name = "account.move.inverted.wizard"
    _description = "Wizard for Delete Reverted Moves"

    journal_id   = fields.Many2one(
        'account.journal', 
        domain="[('type', '=', 'general')]",
        string="Journal", 
        help="Select the Jornal the has reverted moves")
      
    date_start = fields.Date(
        string='From',
        help='From this date reverted moves will be search',
        default=date.today()
    )

    date_end = fields.Date(
        string='To',
        help='To this date reverted moves will be search',
        default=date.today()
    )

    def find_reverted_moves(self):

        moveobj = self.env['account.move']
        revertedobj = self.env['account.move.invertedmoves.wizard']

        domain = [('journal_id', '=', self.journal_id.id),
                  ('date', '>=', self.date_start ),
                  ('date', '<=', self.date_end),
                  ('reversed_entry_id', '!=', False),
                  ('state', '=', 'posted')
                ]
       
        moves = moveobj.search(domain)
        reverted_moves = []
        
        for move in moves:
            id = revertedobj.create( 
                {
                    'reverted_move_id': move.id,
                    'origin_move_id': move.reversed_entry_id.id,
                })
            reverted_moves.append(id.id)

        action = self.env['ir.actions.actions']._for_xml_id('ent_bank_import.action_invertedmoves_wizard_tree')
        action['domain'] = [('id', 'in', reverted_moves)]

        return action


class RevertedAccountMoves(models.TransientModel):
    _name = 'account.move.invertedmoves.wizard'

    reverted_move_id = fields.Many2one(
        'account.move', 
        string="Reverted", 
        help="Reverted move",
        readonly=True
    )

    date_reverted = fields.Date(
        string="R Date",
        help="Reverted move was on this date",
        related="reverted_move_id.date",
        readonly=True
    )

    origin_move_id = fields.Many2one(
        'account.move', 
        string="Origin", 
        help="Origin move",
        readonly=True
    )

    date_origin = fields.Date(
        string="O Date",
        help="Origin move was on this date",
        related="origin_move_id.date",
        readonly=True
    )

    def action_delete_reverted_moves(self):

        reverted = self.mapped('reverted_move_id')
        origin = self.mapped('origin_move_id')
        moves = reverted + origin
        moves.button_draft()
        moves.unlink()
        self.unlink()

        # for move in self:
        #     move.reverted_move_id.button_draft()
        #     move.origin_move_id.button_draft()



