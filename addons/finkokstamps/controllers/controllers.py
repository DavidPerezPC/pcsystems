# -*- coding: utf-8 -*-
# from odoo import http


# class FinkokStamps(http.Controller):
#     @http.route('/finkok_stamps/finkok_stamps', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/finkok_stamps/finkok_stamps/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('finkok_stamps.listing', {
#             'root': '/finkok_stamps/finkok_stamps',
#             'objects': http.request.env['finkok_stamps.finkok_stamps'].search([]),
#         })

#     @http.route('/finkok_stamps/finkok_stamps/objects/<model("finkok_stamps.finkok_stamps"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('finkok_stamps.object', {
#             'object': obj
#         })
