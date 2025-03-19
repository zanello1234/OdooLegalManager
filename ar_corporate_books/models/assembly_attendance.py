# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AssemblyAttendance(models.Model):
    _name = 'ar.assembly.attendance'
    _description = 'Assembly Attendance'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'meeting_date desc, id desc'

    name = fields.Char('Reference', compute='_compute_name', store=True)
    meeting_id = fields.Many2one('ar.meeting.minute', string='Meeting', required=True, tracking=True,
                                domain=[('meeting_type', 'in', ['annual', 'extraordinary'])])
    meeting_date = fields.Datetime('Meeting Date', required=True, tracking=True)
    meeting_type = fields.Selection(related='meeting_id.meeting_type', string='Meeting Type', store=True)
    shareholder_id = fields.Many2one('ar.shareholder', string='Shareholder', required=True, tracking=True)
    proxy_id = fields.Many2one('res.partner', string='Proxy Representative')
    book_id = fields.Many2one('ar.corporate.book', string='Attendance Book', 
                             domain=[('book_type', '=', 'attendance')], required=True, tracking=True)
    folio_number = fields.Integer('Folio Number', required=True, tracking=True)
    attendance_type = fields.Selection([
        ('in_person', 'In Person'),
        ('proxy', 'By Proxy'),
        ('remote', 'Remote Attendance'),
        ('written_vote', 'Written Vote')
    ], string='Attendance Type', required=True, default='in_person', tracking=True)
    shares_represented = fields.Integer('Shares Represented', required=True, tracking=True)
    share_percentage = fields.Float('Share Percentage (%)', compute='_compute_share_percentage', store=True)
    arrival_time = fields.Datetime('Arrival Time')
    departure_time = fields.Datetime('Departure Time')
    attendance_proof = fields.Binary('Attendance Proof', attachment=True)
    attendance_proof_filename = fields.Char('Proof Filename')
    notes = fields.Text('Notes')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('registered', 'Registered'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', tracking=True)
    
    @api.depends('meeting_id', 'shareholder_id')
    def _compute_name(self):
        for record in self:
            if record.meeting_id and record.shareholder_id:
                record.name = _("%s - %s") % (record.meeting_id.name, record.shareholder_id.name)
            else:
                record.name = _("New Attendance")

    @api.depends('shares_represented', 'meeting_id')
    def _compute_share_percentage(self):
        for record in self:
            if record.meeting_id:
                total_shares = sum(self.env['ar.shareholder'].search([
                    ('company_id', '=', record.company_id.id),
                    ('state', '=', 'active')
                ]).mapped('shares_count'))
                
                if total_shares:
                    record.share_percentage = (record.shares_represented / total_shares) * 100
                else:
                    record.share_percentage = 0.0
            else:
                record.share_percentage = 0.0

    @api.onchange('shareholder_id')
    def _onchange_shareholder_id(self):
        if self.shareholder_id:
            self.shares_represented = self.shareholder_id.shares_count

    @api.onchange('meeting_id')
    def _onchange_meeting_id(self):
        if self.meeting_id:
            self.meeting_date = self.meeting_id.meeting_date

    @api.onchange('book_id')
    def _onchange_book_id(self):
        if self.book_id:
            self.folio_number = self.book_id.current_folio

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

    @api.constrains('shares_represented', 'shareholder_id')
    def _check_shares_represented(self):
        for record in self:
            if record.shares_represented <= 0:
                raise ValidationError(_("Shares represented must be greater than 0."))
            
            if record.shares_represented > record.shareholder_id.shares_count:
                raise ValidationError(_("Shares represented cannot exceed the shareholder's total shares."))

    @api.constrains('meeting_id', 'shareholder_id')
    def _check_duplicate_attendance(self):
        for record in self:
            duplicate = self.search([
                ('id', '!=', record.id),
                ('meeting_id', '=', record.meeting_id.id),
                ('shareholder_id', '=', record.shareholder_id.id),
                ('state', '=', 'registered')
            ], limit=1)
            
            if duplicate:
                raise ValidationError(_("This shareholder is already registered for this meeting."))

    def action_register(self):
        for record in self:
            # Update the folios used in the book
            if record.book_id.folios_used < record.folio_number:
                record.book_id.write({'folios_used': record.folio_number})
            
            # Add shareholder to meeting's present shareholders if not already there
            if record.meeting_id and record.shareholder_id.id not in record.meeting_id.present_shareholder_ids.ids:
                record.meeting_id.write({
                    'present_shareholder_ids': [(4, record.shareholder_id.id)]
                })
            
            record.write({'state': 'registered'})

    def action_cancel(self):
        for record in self:
            # Remove shareholder from meeting's present shareholders
            if record.meeting_id and record.state == 'registered':
                record.meeting_id.write({
                    'present_shareholder_ids': [(3, record.shareholder_id.id)]
                })
            
            record.write({'state': 'cancelled'})

    def action_draft(self):
        self.write({'state': 'draft'})

    def action_print_certificate(self):
        self.ensure_one()
        return self.env.ref('ar_corporate_books.action_report_attendance_certificate').report_action(self)
