# -*- coding: utf-8 -*-
# from odoo import http


# class Venuslift(http.Controller):
#     @http.route('/venuslift/venuslift/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/venuslift/venuslift/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('venuslift.listing', {
#             'root': '/venuslift/venuslift',
#             'objects': http.request.env['venuslift.venuslift'].search([]),
#         })

#     @http.route('/venuslift/venuslift/objects/<model("venuslift.venuslift"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('venuslift.object', {
#             'object': obj
#         })
