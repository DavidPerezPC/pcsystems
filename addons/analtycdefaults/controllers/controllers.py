# -*- coding: utf-8 -*-
# from odoo import http


# class Credits(http.Controller):
#     @http.route('/credits/credits/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/credits/credits/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('credits.listing', {
#             'root': '/credits/credits',
#             'objects': http.request.env['credits.credits'].search([]),
#         })

#     @http.route('/credits/credits/objects/<model("credits.credits"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('credits.object', {
#             'object': obj
#         })
