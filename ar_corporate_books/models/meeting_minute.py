# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from datetime import datetime


class MeetingMinute(models.Model):
    _name = 'ar.meeting.minute'
    _description = 'Meeting Minute'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'meeting_date desc, id desc'

    name = fields.Char('Minute Number', required=True, tracking=True, default=lambda self: _('New'))
    meeting_date = fields.Datetime('Meeting Date', required=True, default=fields.Datetime.now, tracking=True)
    book_id = fields.Many2one('ar.corporate.book', string='Book', required=True, tracking=True,
                              domain=[('book_type', 'in', ['board_minutes', 'shareholder_minutes'])])
    meeting_type = fields.Selection([
        ('board', 'Board of Directors Meeting'),
        ('annual', 'Annual Shareholders Meeting'),
        ('extraordinary', 'Extraordinary Shareholders Meeting'),
        ('other', 'Other')
    ], string='Meeting Type', required=True, tracking=True)
    location = fields.Char('Location', required=True, tracking=True)
    folio_start = fields.Integer('Starting Folio', required=True, tracking=True)
    folio_end = fields.Integer('Ending Folio', tracking=True)
    president_id = fields.Many2one('res.partner', string='President', tracking=True)
    secretary_id = fields.Many2one('res.partner', string='Secretary', tracking=True)
    quorum = fields.Float('Quorum (%)', tracking=True)
    present_shareholder_ids = fields.Many2many('ar.shareholder', string='Present Shareholders')
    attendee_ids = fields.Many2many('res.partner', string='Attendees')
    agenda_items = fields.Text('Agenda', required=True)
    content = fields.Html('Minute Content', required=True)
    conclusions = fields.Text('Conclusions')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('approved', 'Approved'),
        ('canceled', 'Canceled')
    ], string='Status', default='draft', tracking=True)
    attachment_ids = fields.Many2many('ir.attachment', string='Attachments')
    folios_count = fields.Integer(compute='_compute_folios_count', string='Folios Count')
    signature_ids = fields.One2many('ar.meeting.minute.signature', 'minute_id', string='Signatures')
    
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
            if record.folio_start <= 0:
                raise ValidationError(_("Starting folio must be greater than 0."))
            
            if record.folio_end and record.folio_end < record.folio_start:
                raise ValidationError(_("Ending folio cannot be less than starting folio."))
            
            if record.folio_end and record.folio_end > record.book_id.folios:
                raise ValidationError(_("Ending folio cannot exceed the total number of folios in the book."))
            
            # Check overlapping folios for the same book
            overlapping = self.search([
                ('id', '!=', record.id),
                ('book_id', '=', record.book_id.id),
                ('state', 'in', ['confirmed', 'approved']),
                '|',
                '&', ('folio_start', '<=', record.folio_start), ('folio_end', '>=', record.folio_start),
                '&', ('folio_start', '<=', record.folio_end), ('folio_end', '>=', record.folio_end)
            ], limit=1)
            
            if overlapping:
                raise ValidationError(_("The folios range overlaps with an existing minute record."))

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            seq_date = fields.Date.context_today(self)
            vals['name'] = self.env['ir.sequence'].next_by_code('ar.meeting.minute', sequence_date=seq_date) or _('New')
        return super(MeetingMinute, self).create(vals)

    @api.onchange('book_id')
    def _onchange_book_id(self):
        if self.book_id:
            self.folio_start = self.book_id.current_folio

    @api.onchange('meeting_type')
    def _onchange_meeting_type(self):
        if self.meeting_type:
            if self.meeting_type == 'board':
                self.book_id = self.env['ar.corporate.book'].search([
                    ('book_type', '=', 'board_minutes'),
                    ('company_id', '=', self.env.company.id),
                    ('state', '=', 'active')
                ], limit=1)
            elif self.meeting_type in ['annual', 'extraordinary']:
                self.book_id = self.env['ar.corporate.book'].search([
                    ('book_type', '=', 'shareholder_minutes'),
                    ('company_id', '=', self.env.company.id),
                    ('state', '=', 'active')
                ], limit=1)

    def action_confirm(self):
        for record in self:
            # Check if ending folio is set
            if not record.folio_end:
                raise ValidationError(_("Please set the ending folio before confirming."))
            record.write({'state': 'confirmed'})

    def action_approve(self):
        for record in self:
            # Update the folios used in the book if the end folio is greater
            if record.book_id.folios_used < record.folio_end:
                record.book_id.write({'folios_used': record.folio_end})
            
            # Record attendance in the assembly attendance module if it's a shareholder meeting
            if record.meeting_type in ['annual', 'extraordinary']:
                attendance_book = self.env['ar.corporate.book'].search([
                    ('book_type', '=', 'attendance'),
                    ('company_id', '=', self.env.company.id),
                    ('state', '=', 'active')
                ], limit=1)
                
                if attendance_book and record.present_shareholder_ids:
                    next_folio = attendance_book.current_folio
                    for shareholder in record.present_shareholder_ids:
                        self.env['ar.assembly.attendance'].create({
                            'meeting_id': record.id,
                            'shareholder_id': shareholder.id,
                            'meeting_date': record.meeting_date,
                            'book_id': attendance_book.id,
                            'folio_number': next_folio,
                            'shares_represented': shareholder.shares_count,
                            'attendance_type': 'in_person',
                            'state': 'registered'
                        })
                        next_folio += 1
                    
                    # Update folios in attendance book
                    attendance_book.write({'folios_used': next_folio - 1})
            
            record.write({'state': 'approved'})

    def action_cancel(self):
        self.write({'state': 'canceled'})

    def action_draft(self):
        self.write({'state': 'draft'})

    def action_add_signature(self):
        self.ensure_one()
        return {
            'name': _('Add Signature'),
            'type': 'ir.actions.act_window',
            'res_model': 'ar.meeting.minute.add.signature.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_minute_id': self.id},
        }

    def action_view_attendees(self):
        self.ensure_one()
        return {
            'name': _('Attendees'),
            'view_mode': 'tree,form',
            'res_model': 'res.partner',
            'domain': [('id', 'in', self.attendee_ids.ids)],
            'type': 'ir.actions.act_window',
        }

    def action_generate_pdf(self):
        self.ensure_one()
        return self.env.ref('ar_corporate_books.action_report_meeting_minute').report_action(self)


class MeetingMinuteSignature(models.Model):
    _name = 'ar.meeting.minute.signature'
    _description = 'Meeting Minute Signature'
    _order = 'sequence, id'

    minute_id = fields.Many2one('ar.meeting.minute', string='Minute', required=True, ondelete='cascade')
    partner_id = fields.Many2one('res.partner', string='Person', required=True)
    role = fields.Selection([
        ('president', 'President'),
        ('secretary', 'Secretary'),
        ('director', 'Director'),
        ('shareholder', 'Shareholder'),
        ('witness', 'Witness'),
        ('other', 'Other')
    ], string='Role', required=True)
    signature_date = fields.Date('Signature Date', default=fields.Date.context_today)
    sequence = fields.Integer('Sequence', default=10)
    notes = fields.Text('Notes')
    
    _sql_constraints = [
        ('minute_partner_role_uniq', 'unique(minute_id, partner_id, role)', 
         'A person can sign only once with the same role for a minute!')
    ]
