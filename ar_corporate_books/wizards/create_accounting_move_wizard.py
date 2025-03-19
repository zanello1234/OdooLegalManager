# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class CreateAccountingMoveWizard(models.TransientModel):
    _name = 'ar.create.accounting.move.wizard'
    _description = 'Create Journal Entry from Accounting Book'

    accounting_book_id = fields.Many2one('ar.accounting.book', string='Accounting Book Entry', required=True, readonly=True)
    journal_id = fields.Many2one('account.journal', string='Journal', required=True, domain=[('type', 'in', ['general', 'sale', 'purchase'])])
    date = fields.Date(string='Date', required=True, default=fields.Date.context_today)
    reference = fields.Char(string='Reference', required=True)
    line_ids = fields.One2many('ar.create.accounting.move.line.wizard', 'wizard_id', string='Journal Items', required=True)
    company_id = fields.Many2one('res.company', related='accounting_book_id.company_id', readonly=True)
    currency_id = fields.Many2one('res.currency', related='accounting_book_id.currency_id', readonly=True)
    
    @api.onchange('accounting_book_id')
    def _onchange_accounting_book_id(self):
        if self.accounting_book_id:
            self.reference = self.accounting_book_id.name
            self.date = self.accounting_book_id.date
            
            # Create a default debit and credit line based on accounting book entry
            if self.accounting_book_id.account_id and self.accounting_book_id.amount:
                lines = []
                
                # Debit line
                lines.append((0, 0, {
                    'account_id': self.accounting_book_id.account_id.id,
                    'name': self.accounting_book_id.name,
                    'debit': self.accounting_book_id.amount,
                    'credit': 0.0,
                    'partner_id': self.accounting_book_id.partner_id.id,
                }))
                
                # Credit line
                lines.append((0, 0, {
                    'account_id': False,  # To be filled by user
                    'name': self.accounting_book_id.name,
                    'debit': 0.0,
                    'credit': self.accounting_book_id.amount,
                    'partner_id': self.accounting_book_id.partner_id.id,
                }))
                
                self.line_ids = lines

    @api.constrains('line_ids')
    def _check_balance(self):
        for wizard in self:
            if wizard.line_ids:
                total_debit = sum(wizard.line_ids.mapped('debit'))
                total_credit = sum(wizard.line_ids.mapped('credit'))
                if round(total_debit, 2) != round(total_credit, 2):
                    raise ValidationError(_("The journal entry is not balanced. Total debit: %s, Total credit: %s") % 
                                         (total_debit, total_credit))

    def action_create_move(self):
        self.ensure_one()
        
        # Check if all accounts are filled
        if any(not line.account_id for line in self.line_ids):
            raise ValidationError(_("All journal items must have an account."))
        
        # Create the journal entry
        move_vals = {
            'journal_id': self.journal_id.id,
            'date': self.date,
            'ref': self.reference,
            'line_ids': [(0, 0, {
                'account_id': line.account_id.id,
                'name': line.name,
                'debit': line.debit,
                'credit': line.credit,
                'partner_id': line.partner_id.id,
                'analytic_account_id': line.analytic_account_id.id if line.analytic_account_id else False,
            }) for line in self.line_ids],
        }
        
        move = self.env['account.move'].create(move_vals)
        
        # Link the move to the accounting book entry
        self.accounting_book_id.write({
            'move_id': move.id,
        })
        
        # Post a message in the chatter
        msg = _("Journal entry created: <a href=# data-oe-model=account.move data-oe-id=%d>%s</a>") % (move.id, move.name)
        self.accounting_book_id.message_post(body=msg)
        
        return {
            'name': _('Journal Entry'),
            'view_mode': 'form',
            'res_model': 'account.move',
            'res_id': move.id,
            'type': 'ir.actions.act_window',
        }


class CreateAccountingMoveLineWizard(models.TransientModel):
    _name = 'ar.create.accounting.move.line.wizard'
    _description = 'Journal Entry Line for Accounting Book'

    wizard_id = fields.Many2one('ar.create.accounting.move.wizard', string='Wizard', required=True, ondelete='cascade')
    account_id = fields.Many2one('account.account', string='Account', required=True)
    name = fields.Char(string='Label', required=True)
    debit = fields.Monetary(string='Debit', default=0.0, currency_field='currency_id')
    credit = fields.Monetary(string='Credit', default=0.0, currency_field='currency_id')
    partner_id = fields.Many2one('res.partner', string='Partner')
    analytic_account_id = fields.Many2one('account.analytic.account', string='Analytic Account')
    currency_id = fields.Many2one('res.currency', related='wizard_id.currency_id', readonly=True)

    @api.onchange('debit')
    def _onchange_debit(self):
        if self.debit:
            self.credit = 0.0

    @api.onchange('credit')
    def _onchange_credit(self):
        if self.credit:
            self.debit = 0.0
