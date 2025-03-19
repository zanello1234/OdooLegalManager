# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class BookInventory(models.Model):
    _name = 'ar.book.inventory'
    _description = 'Book Inventory'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char('Reference', required=True, tracking=True, default=lambda self: _('New'))
    date = fields.Date('Date', required=True, default=fields.Date.context_today, tracking=True)
    book_id = fields.Many2one('ar.corporate.book', string='Book', required=True, tracking=True)
    folio_start = fields.Integer('Starting Folio', required=True, tracking=True)
    folio_end = fields.Integer('Ending Folio', required=True, tracking=True)
    item_description = fields.Text('Description', required=True)
    item_value = fields.Monetary('Value', currency_field='currency_id', tracking=True)
    currency_id = fields.Many2one('res.currency', string='Currency',
                                  default=lambda self: self.env.company.currency_id)
    location_id = fields.Many2one('stock.location', string='Location')
    responsible_id = fields.Many2one('res.users', string='Responsible', 
                                     default=lambda self: self.env.user, tracking=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('validated', 'Validated'),
        ('canceled', 'Canceled')
    ], string='Status', default='draft', tracking=True)
    attachment_ids = fields.Many2many('ir.attachment', string='Attachments')
    folios_count = fields.Integer(compute='_compute_folios_count', string='Folios Count')
    
    @api.depends('folio_start', 'folio_end')
    def _compute_folios_count(self):
        for record in self:
            if record.folio_start and record.folio_end and record.folio_end >= record.folio_start:
                record.folios_count = record.folio_end - record.folio_start + 1
            else:
                record.folios_count = 0

    @api.constrains('folio_start', 'folio_end', 'book_id')
    def _check_folios(self):
        for record in self:
            if record.folio_start <= 0 or record.folio_end <= 0:
                raise ValidationError(_("Folio numbers must be greater than 0."))
            
            if record.folio_end < record.folio_start:
                raise ValidationError(_("Ending folio cannot be less than starting folio."))
            
            if record.folio_end > record.book_id.folios:
                raise ValidationError(_("Ending folio cannot exceed the total number of folios in the book."))
            
            # Check overlapping folios for the same book
            overlapping = self.search([
                ('id', '!=', record.id),
                ('book_id', '=', record.book_id.id),
                ('state', '=', 'validated'),
                '|',
                '&', ('folio_start', '<=', record.folio_start), ('folio_end', '>=', record.folio_start),
                '&', ('folio_start', '<=', record.folio_end), ('folio_end', '>=', record.folio_end)
            ], limit=1)
            
            if overlapping:
                raise ValidationError(_("The folios range overlaps with an existing inventory record."))

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            seq_date = fields.Date.context_today(self)
            vals['name'] = self.env['ir.sequence'].next_by_code('ar.book.inventory', sequence_date=seq_date) or _('New')
        return super(BookInventory, self).create(vals)

    @api.onchange('book_id')
    def _onchange_book_id(self):
        if self.book_id:
            self.folio_start = self.book_id.current_folio

    def action_validate(self):
        for record in self:
            # Update the folios used in the book if the end folio is greater
            if record.book_id.folios_used < record.folio_end:
                record.book_id.write({'folios_used': record.folio_end})
            record.write({'state': 'validated'})

    def action_cancel(self):
        self.write({'state': 'canceled'})

    def action_draft(self):
        self.write({'state': 'draft'})

    def action_view_attachments(self):
        self.ensure_one()
        return {
            'name': _('Attachments'),
            'view_mode': 'tree,form',
            'res_model': 'ir.attachment',
            'domain': [('id', 'in', self.attachment_ids.ids)],
            'type': 'ir.actions.act_window',
            'context': {'create': False},
        }
