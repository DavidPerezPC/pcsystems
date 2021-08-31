# -*- coding: utf-8 -*-
# from odoo import http


# class Farmerscredit(http.Controller):
#     @http.route('/farmerscredit/farmerscredit/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/farmerscredit/farmerscredit/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('farmerscredit.listing', {
#             'root': '/farmerscredit/farmerscredit',
#             'objects': http.request.env['farmerscredit.farmerscredit'].search([]),
#         })

#     @http.route('/farmerscredit/farmerscredit/objects/<model("farmerscredit.farmerscredit"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('farmerscredit.object', {
#             'object': obj
#         })
