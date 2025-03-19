# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AccountingBook(models.Model):
    _name = 'ar.accounting.book'
    _description = 'Argentine Accounting Book'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char('Entry Name', required=True, tracking=True)
    date = fields.Date('Date', required=True, default=fields.Date.context_today, tracking=True)
    book_id = fields.Many2one('ar.corporate.book', string='Book', required=True, tracking=True,
                              domain=[('book_type', 'in', ['journal', 'ledger', 'inventory'])])
    folio_number = fields.Integer('Folio Number', required=True, tracking=True)
    entry_number = fields.Char('Entry Number', required=True, tracking=True)
    description = fields.Text('Description', required=True)
    amount = fields.Monetary('Amount', currency_field='currency_id', tracking=True)
    currency_id = fields.Many2one('res.currency', string='Currency',
                                  default=lambda self: self.env.company.currency_id)
    move_id = fields.Many2one('account.move', string='Journal Entry', tracking=True)
    partner_id = fields.Many2one('res.partner', string='Partner')
    account_id = fields.Many2one('account.account', string='Account')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('posted', 'Posted'),
        ('canceled', 'Canceled')
    ], string='Status', default='draft', tracking=True)
    attachment_ids = fields.Many2many('ir.attachment', string='Attachments')

    @api.constrains('folio_number', 'book_id')
    def _check_folio_number(self):
        for record in self:
            if record.folio_number <= 0:
                raise ValidationError(_("Folio number must be greater than 0."))
            
            if record.folio_number > record.book_id.folios:
                raise ValidationError(_("Folio number cannot exceed the total number of folios in the book."))
            
            # Check duplicate folio for the same book
            duplicate = self.search([
                ('id', '!=', record.id),
                ('book_id', '=', record.book_id.id),
                ('folio_number', '=', record.folio_number)
            ], limit=1)
            
            if duplicate:
                raise ValidationError(_("Folio number %s is already used in this book.") % record.folio_number)

    @api.onchange('book_id')
    def _onchange_book_id(self):
        if self.book_id:
            self.folio_number = self.book_id.current_folio

    def action_post(self):
        for record in self:
            # Update the folios used in the book
            if record.book_id.folios_used < record.folio_number:
                record.book_id.write({'folios_used': record.folio_number})
            record.write({'state': 'posted'})

    def action_cancel(self):
        self.write({'state': 'canceled'})

    def action_view_move(self):
        self.ensure_one()
        if not self.move_id:
            return {}
        
        return {
            'name': _('Journal Entry'),
            'view_mode': 'form',
            'res_model': 'account.move',
            'res_id': self.move_id.id,
            'type': 'ir.actions.act_window',
        }

    def action_create_move(self):
        self.ensure_one()
        if self.move_id:
            raise ValidationError(_("This entry already has a journal entry associated."))
        
        return {
            'name': _('Create Journal Entry'),
            'type': 'ir.actions.act_window',
            'res_model': 'ar.create.accounting.move.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_accounting_book_id': self.id},
        }


class AccountMove(models.Model):
    _inherit = 'account.move'

    accounting_book_ids = fields.One2many('ar.accounting.book', 'move_id', string='Accounting Book Entries')
    accounting_book_count = fields.Integer(compute='_compute_accounting_book_count', string='Book Entries')

    def _compute_accounting_book_count(self):
        for move in self:
            move.accounting_book_count = len(move.accounting_book_ids)

    def action_view_accounting_books(self):
        self.ensure_one()
        return {
            'name': _('Accounting Book Entries'),
            'view_mode': 'tree,form',
            'res_model': 'ar.accounting.book',
            'domain': [('move_id', '=', self.id)],
            'type': 'ir.actions.act_window',
            'context': {'default_move_id': self.id},
        }
