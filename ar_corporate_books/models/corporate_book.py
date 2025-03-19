# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import re


class CorporateBook(models.Model):
    _name = 'ar.corporate.book'
    _description = 'Argentine Corporate Book'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char('Book Name', required=True, tracking=True)
    book_number = fields.Char('Book Number', required=True, tracking=True)
    rubric_number = fields.Char('Rubric Number', tracking=True)
    rubric_date = fields.Date('Rubric Date', tracking=True)
    start_date = fields.Date('Start Date', tracking=True)
    end_date = fields.Date('End Date', tracking=True)
    folios = fields.Integer('Number of Folios', default=200, tracking=True)
    folios_used = fields.Integer('Folios Used', default=0, tracking=True)
    book_type = fields.Selection([
        ('board_minutes', 'Board Minutes Book'),
        ('shareholder_minutes', 'Shareholder Minutes Book'),
        ('shareholder_register', 'Shareholder Register Book'),
        ('attendance', 'Attendance Book'),
        ('inventory', 'Inventory Book'),
        ('journal', 'Journal Book'),
        ('ledger', 'Ledger Book'),
        ('other', 'Other')
    ], string='Book Type', required=True, tracking=True)
    authority_id = fields.Many2one('res.partner', string='Issuing Authority', tracking=True)
    active = fields.Boolean(default=True)
    notes = fields.Text('Notes')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('canceled', 'Canceled')
    ], string='Status', default='draft', tracking=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    minute_count = fields.Integer(compute='_compute_minute_count', string='Minutes')
    current_folio = fields.Integer(compute='_compute_current_folio', string='Current Folio')
    documents_count = fields.Integer(compute='_compute_documents_count', string='Related Documents')
    attachment_ids = fields.Many2many('ir.attachment', string='Attachments')
    
    _sql_constraints = [
        ('book_number_company_uniq', 'unique(book_number, company_id)', 
         'Book number must be unique per company!'),
    ]

    @api.depends('folios_used')
    def _compute_current_folio(self):
        for book in self:
            book.current_folio = book.folios_used + 1 if book.folios_used < book.folios else book.folios

    def _compute_minute_count(self):
        for book in self:
            if book.book_type in ['board_minutes', 'shareholder_minutes']:
                book.minute_count = self.env['ar.meeting.minute'].search_count([('book_id', '=', book.id)])
            else:
                book.minute_count = 0

    def _compute_documents_count(self):
        for book in self:
            book.documents_count = len(book.attachment_ids)

    @api.constrains('folios', 'folios_used')
    def _check_folios(self):
        for book in self:
            if book.folios_used > book.folios:
                raise ValidationError(_("The number of folios used cannot exceed the total number of folios."))

    @api.constrains('book_number')
    def _check_book_number(self):
        for book in self:
            if book.book_number and not re.match(r'^[A-Za-z0-9]+$', book.book_number):
                raise ValidationError(_("Book number must contain only letters and numbers."))

    def action_activate(self):
        self.write({'state': 'active'})

    def action_complete(self):
        self.write({'state': 'completed'})

    def action_cancel(self):
        self.write({'state': 'canceled'})

    def action_view_minutes(self):
        self.ensure_one()
        return {
            'name': _('Minutes'),
            'view_mode': 'tree,form',
            'res_model': 'ar.meeting.minute',
            'domain': [('book_id', '=', self.id)],
            'type': 'ir.actions.act_window',
            'context': {'default_book_id': self.id}
        }

    def action_view_documents(self):
        self.ensure_one()
        return {
            'name': _('Related Documents'),
            'view_mode': 'tree,form',
            'res_model': 'ir.attachment',
            'domain': [('id', 'in', self.attachment_ids.ids)],
            'type': 'ir.actions.act_window',
        }

    def action_add_folios(self):
        self.ensure_one()
        return {
            'name': _('Add Used Folios'),
            'type': 'ir.actions.act_window',
            'res_model': 'ar.book.add.folios.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_book_id': self.id, 'default_current_folios': self.folios_used},
        }

    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        args = args or []
        domain = []
        if name:
            domain = ['|', ('name', operator, name), ('book_number', operator, name)]
        return self._search(domain + args, limit=limit, access_rights_uid=name_get_uid)
