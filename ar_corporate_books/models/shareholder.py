# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class Shareholder(models.Model):
    _name = 'ar.shareholder'
    _description = 'Shareholder'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    name = fields.Char('Shareholder Name', related='partner_id.name', store=True, readonly=True)
    partner_id = fields.Many2one('res.partner', string='Contact', required=True, tracking=True)
    identification_type = fields.Selection([
        ('dni', 'DNI'),
        ('cuit', 'CUIT'),
        ('passport', 'Passport'),
        ('other', 'Other')
    ], string='ID Type', required=True, tracking=True)
    identification_number = fields.Char('ID Number', required=True, tracking=True)
    shareholder_number = fields.Char('Shareholder Number', required=True, tracking=True)
    registration_date = fields.Date('Registration Date', required=True, default=fields.Date.context_today, tracking=True)
    shares_count = fields.Integer('Number of Shares', required=True, tracking=True)
    share_percentage = fields.Float('Share Percentage (%)', compute='_compute_share_percentage', store=True)
    share_value = fields.Monetary('Share Value', currency_field='currency_id', tracking=True)
    total_investment = fields.Monetary('Total Investment', compute='_compute_total_investment', 
                                      currency_field='currency_id', store=True)
    currency_id = fields.Many2one('res.currency', string='Currency',
                                  default=lambda self: self.env.company.currency_id)
    book_id = fields.Many2one('ar.corporate.book', string='Shareholder Book', 
                             domain=[('book_type', '=', 'shareholder_register')], tracking=True)
    folio_number = fields.Integer('Folio Number', tracking=True)
    shareholder_type = fields.Selection([
        ('individual', 'Individual'),
        ('company', 'Company'),
        ('other', 'Other')
    ], string='Shareholder Type', required=True, tracking=True)
    state = fields.Selection([
        ('active', 'Active'),
        ('inactive', 'Inactive')
    ], string='Status', default='active', tracking=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    notes = fields.Text('Notes')
    attendance_ids = fields.One2many('ar.assembly.attendance', 'shareholder_id', string='Meeting Attendances')
    attendance_count = fields.Integer(compute='_compute_attendance_count', string='Attendances')
    transaction_ids = fields.One2many('ar.shareholder.transaction', 'shareholder_id', string='Share Transactions')
    transaction_count = fields.Integer(compute='_compute_transaction_count', string='Transactions')
    
    _sql_constraints = [
        ('shareholder_number_company_uniq', 'unique(shareholder_number, company_id)', 
         'Shareholder number must be unique per company!'),
    ]
    
    @api.depends('shares_count', 'company_id')
    def _compute_share_percentage(self):
        for record in self:
            total_shares = sum(self.search([
                ('company_id', '=', record.company_id.id),
                ('state', '=', 'active')
            ]).mapped('shares_count'))
            
            if total_shares:
                record.share_percentage = (record.shares_count / total_shares) * 100
            else:
                record.share_percentage = 0.0

    @api.depends('shares_count', 'share_value')
    def _compute_total_investment(self):
        for record in self:
            record.total_investment = record.shares_count * record.share_value

    def _compute_attendance_count(self):
        for record in self:
            record.attendance_count = len(record.attendance_ids)

    def _compute_transaction_count(self):
        for record in self:
            record.transaction_count = len(record.transaction_ids)

    @api.constrains('shares_count')
    def _check_shares_count(self):
        for record in self:
            if record.shares_count <= 0:
                raise ValidationError(_("Number of shares must be greater than 0."))

    @api.constrains('share_percentage')
    def _check_share_percentage(self):
        for record in self:
            if record.share_percentage < 0 or record.share_percentage > 100:
                raise ValidationError(_("Share percentage must be between 0 and 100."))

    @api.constrains('folio_number', 'book_id')
    def _check_folio_number(self):
        for record in self:
            if record.book_id and record.folio_number:
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

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        if self.partner_id:
            if self.partner_id.is_company:
                self.shareholder_type = 'company'
            else:
                self.shareholder_type = 'individual'
            
            # Set identification info if available
            if hasattr(self.partner_id, 'l10n_ar_afip_responsibility_type_id'):
                if self.partner_id.l10n_ar_afip_responsibility_type_id:
                    self.identification_type = 'cuit'
                    self.identification_number = self.partner_id.vat or ''

    def action_view_attendances(self):
        self.ensure_one()
        return {
            'name': _('Meeting Attendances'),
            'view_mode': 'tree,form',
            'res_model': 'ar.assembly.attendance',
            'domain': [('shareholder_id', '=', self.id)],
            'type': 'ir.actions.act_window',
            'context': {'default_shareholder_id': self.id}
        }

    def action_view_transactions(self):
        self.ensure_one()
        return {
            'name': _('Share Transactions'),
            'view_mode': 'tree,form',
            'res_model': 'ar.shareholder.transaction',
            'domain': [('shareholder_id', '=', self.id)],
            'type': 'ir.actions.act_window',
            'context': {'default_shareholder_id': self.id}
        }

    def action_add_transaction(self):
        self.ensure_one()
        return {
            'name': _('Add Share Transaction'),
            'type': 'ir.actions.act_window',
            'res_model': 'ar.shareholder.transaction.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_shareholder_id': self.id},
        }
    
    def action_generate_certificate(self):
        self.ensure_one()
        return self.env.ref('ar_corporate_books.action_report_shareholder_certificate').report_action(self)


class ShareholderTransaction(models.Model):
    _name = 'ar.shareholder.transaction'
    _description = 'Shareholder Transaction'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'
    
    name = fields.Char('Reference', required=True, tracking=True, default=lambda self: _('New'))
    date = fields.Date('Transaction Date', required=True, default=fields.Date.context_today, tracking=True)
    shareholder_id = fields.Many2one('ar.shareholder', string='Shareholder', required=True, tracking=True)
    transaction_type = fields.Selection([
        ('purchase', 'Purchase'),
        ('sale', 'Sale'),
        ('transfer_in', 'Transfer In'),
        ('transfer_out', 'Transfer Out'),
        ('inheritance', 'Inheritance'),
        ('donation', 'Donation'),
        ('other', 'Other')
    ], string='Transaction Type', required=True, tracking=True)
    partner_id = fields.Many2one('res.partner', string='Counterpart', tracking=True)
    shares_count = fields.Integer('Number of Shares', required=True, tracking=True)
    share_price = fields.Monetary('Share Price', currency_field='currency_id', tracking=True)
    total_amount = fields.Monetary('Total Amount', compute='_compute_total_amount', 
                                  currency_field='currency_id', store=True)
    currency_id = fields.Many2one('res.currency', string='Currency',
                                 default=lambda self: self.env.company.currency_id)
    book_id = fields.Many2one('ar.corporate.book', string='Corporate Book', 
                            domain=[('book_type', '=', 'shareholder_register')], tracking=True)
    folio_number = fields.Integer('Folio Number', tracking=True)
    notes = fields.Text('Notes')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', tracking=True)
    attachment_ids = fields.Many2many('ir.attachment', string='Attachments')
    
    @api.depends('shares_count', 'share_price')
    def _compute_total_amount(self):
        for record in self:
            record.total_amount = record.shares_count * record.share_price

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            seq_date = fields.Date.context_today(self)
            vals['name'] = self.env['ir.sequence'].next_by_code('ar.shareholder.transaction', sequence_date=seq_date) or _('New')
        return super(ShareholderTransaction, self).create(vals)

    @api.onchange('book_id')
    def _onchange_book_id(self):
        if self.book_id:
            self.folio_number = self.book_id.current_folio

    @api.constrains('shares_count')
    def _check_shares_count(self):
        for record in self:
            if record.shares_count <= 0:
                raise ValidationError(_("Number of shares must be greater than 0."))

    def action_confirm(self):
        for record in self:
            # Update shareholder's shares count based on transaction type
            shareholder = record.shareholder_id
            if record.transaction_type in ['purchase', 'transfer_in', 'inheritance', 'donation']:
                shareholder.write({'shares_count': shareholder.shares_count + record.shares_count})
            elif record.transaction_type in ['sale', 'transfer_out']:
                if shareholder.shares_count < record.shares_count:
                    raise ValidationError(_("Shareholder doesn't have enough shares for this transaction."))
                shareholder.write({'shares_count': shareholder.shares_count - record.shares_count})
            
            # Update book folios if applicable
            if record.book_id and record.folio_number:
                if record.book_id.folios_used < record.folio_number:
                    record.book_id.write({'folios_used': record.folio_number})
            
            record.write({'state': 'confirmed'})

    def action_cancel(self):
        for record in self:
            if record.state == 'confirmed':
                # Revert shareholder's shares count
                shareholder = record.shareholder_id
                if record.transaction_type in ['purchase', 'transfer_in', 'inheritance', 'donation']:
                    shareholder.write({'shares_count': shareholder.shares_count - record.shares_count})
                elif record.transaction_type in ['sale', 'transfer_out']:
                    shareholder.write({'shares_count': shareholder.shares_count + record.shares_count})
            
            record.write({'state': 'cancelled'})

    def action_draft(self):
        self.write({'state': 'draft'})
