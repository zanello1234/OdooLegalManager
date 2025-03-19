# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ShareholderTransactionWizard(models.TransientModel):
    _name = 'ar.shareholder.transaction.wizard'
    _description = 'Add Shareholder Transaction'

    shareholder_id = fields.Many2one('ar.shareholder', string='Shareholder', required=True, readonly=True)
    transaction_type = fields.Selection([
        ('purchase', 'Purchase'),
        ('sale', 'Sale'),
        ('transfer_in', 'Transfer In'),
        ('transfer_out', 'Transfer Out'),
        ('inheritance', 'Inheritance'),
        ('donation', 'Donation'),
        ('other', 'Other')
    ], string='Transaction Type', required=True, default='purchase')
    date = fields.Date(string='Transaction Date', required=True, default=fields.Date.context_today)
    partner_id = fields.Many2one('res.partner', string='Counterpart')
    shares_count = fields.Integer(string='Number of Shares', required=True, default=1)
    share_price = fields.Monetary(string='Share Price', required=True, currency_field='currency_id')
    total_amount = fields.Monetary(string='Total Amount', compute='_compute_total_amount', store=True, currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', string='Currency', required=True,
                                  default=lambda self: self.env.company.currency_id)
    book_id = fields.Many2one('ar.corporate.book', string='Corporate Book', 
                             domain=[('book_type', '=', 'shareholder_register')])
    folio_number = fields.Integer(string='Folio Number')
    notes = fields.Text(string='Notes')
    
    @api.depends('shares_count', 'share_price')
    def _compute_total_amount(self):
        for record in self:
            record.total_amount = record.shares_count * record.share_price

    @api.onchange('transaction_type')
    def _onchange_transaction_type(self):
        # Make partner_id required for certain transaction types
        if self.transaction_type in ['purchase', 'sale', 'transfer_in', 'transfer_out']:
            return {'warning': {'title': _('Counterpart Required'), 
                               'message': _('Please specify the counterpart for this transaction type.')}}

    @api.onchange('book_id')
    def _onchange_book_id(self):
        if self.book_id:
            self.folio_number = self.book_id.current_folio

    @api.constrains('shares_count')
    def _check_shares_count(self):
        for record in self:
            if record.shares_count <= 0:
                raise ValidationError(_("Number of shares must be greater than 0."))
                
            # Check if shareholder has enough shares for outgoing transactions
            if record.transaction_type in ['sale', 'transfer_out'] and record.shares_count > record.shareholder_id.shares_count:
                raise ValidationError(_("Shareholder doesn't have enough shares for this transaction. Available: %s", 
                                       record.shareholder_id.shares_count))

    @api.constrains('folio_number', 'book_id')
    def _check_folio_number(self):
        for record in self:
            if record.book_id and record.folio_number:
                if record.folio_number <= 0:
                    raise ValidationError(_("Folio number must be greater than 0."))
                
                if record.folio_number > record.book_id.folios:
                    raise ValidationError(_("Folio number cannot exceed the total number of folios in the book."))
                
                # Check duplicate folio for the same book
                duplicate = self.env['ar.shareholder.transaction'].search([
                    ('book_id', '=', record.book_id.id),
                    ('folio_number', '=', record.folio_number),
                    ('state', '!=', 'cancelled')
                ], limit=1)
                
                if duplicate:
                    raise ValidationError(_("Folio number %s is already used in this book.") % record.folio_number)

    def action_create_transaction(self):
        self.ensure_one()
        
        # Create the transaction
        transaction_vals = {
            'shareholder_id': self.shareholder_id.id,
            'transaction_type': self.transaction_type,
            'date': self.date,
            'partner_id': self.partner_id.id,
            'shares_count': self.shares_count,
            'share_price': self.share_price,
            'book_id': self.book_id.id if self.book_id else False,
            'folio_number': self.folio_number if self.folio_number else False,
            'notes': self.notes,
            'company_id': self.shareholder_id.company_id.id,
            'currency_id': self.currency_id.id,
        }
        
        transaction = self.env['ar.shareholder.transaction'].create(transaction_vals)
        
        # Automatically confirm the transaction
        transaction.action_confirm()
        
        return {
            'name': _('Share Transaction'),
            'view_mode': 'form',
            'res_model': 'ar.shareholder.transaction',
            'res_id': transaction.id,
            'type': 'ir.actions.act_window',
            'target': 'current',
        }
