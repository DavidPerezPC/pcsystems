# -*- coding: utf-8 -*-

import logging
import re

from odoo import models, api

_logger = logging.getLogger(__name__)

class AccountEdiFormat(models.Model):
    _inherit = 'account.edi.format'

    