# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class MeetingMinuteAddSignatureWizard(models.TransientModel):
    _name = 'ar.meeting.minute.add.signature.wizard'
    _description = 'Add Signature to Meeting Minute'

    minute_id = fields.Many2one('ar.meeting.minute', string='Minute', required=True, readonly=True)
    partner_id = fields.Many2one('res.partner', string='Person', required=True)
    role = fields.Selection([
        ('president', 'President'),
        ('secretary', 'Secretary'),
        ('director', 'Director'),
        ('shareholder', 'Shareholder'),
        ('witness', 'Witness'),
        ('other', 'Other')
    ], string='Role', required=True, default='director')
    signature_date = fields.Date(string='Signature Date', required=True, default=fields.Date.context_today)
    notes = fields.Text(string='Notes')
    sequence = fields.Integer(string='Sequence', default=10)
    
    @api.onchange('role')
    def _onchange_role(self):
        # Auto-fill partner based on role
        if self.role == 'president' and self.minute_id.president_id:
            self.partner_id = self.minute_id.president_id
        elif self.role == 'secretary' and self.minute_id.secretary_id:
            self.partner_id = self.minute_id.secretary_id

    @api.constrains('partner_id', 'role', 'minute_id')
    def _check_duplicate_signature(self):
        for record in self:
            # Check if this person already signed with the same role
            existing = self.env['ar.meeting.minute.signature'].search([
                ('minute_id', '=', record.minute_id.id),
                ('partner_id', '=', record.partner_id.id),
                ('role', '=', record.role)
            ], limit=1)
            
            if existing:
                raise ValidationError(_("%s has already signed as %s for this minute.") % 
                                     (record.partner_id.name, record.role))

    def action_add_signature(self):
        self.ensure_one()
        
        # Create the signature
        signature_vals = {
            'minute_id': self.minute_id.id,
            'partner_id': self.partner_id.id,
            'role': self.role,
            'signature_date': self.signature_date,
            'notes': self.notes,
            'sequence': self.sequence,
        }
        
        signature = self.env['ar.meeting.minute.signature'].create(signature_vals)
        
        # Update president/secretary in the minute if they are signing
        update_vals = {}
        if self.role == 'president' and not self.minute_id.president_id:
            update_vals['president_id'] = self.partner_id.id
        elif self.role == 'secretary' and not self.minute_id.secretary_id:
            update_vals['secretary_id'] = self.partner_id.id
            
        if update_vals:
            self.minute_id.write(update_vals)
        
        # Post message in the chatter
        msg = _("%s signed the minute as %s on %s") % (
            self.partner_id.name, 
            dict(self._fields['role'].selection).get(self.role), 
            self.signature_date
        )
        self.minute_id.message_post(body=msg)
        
        return {'type': 'ir.actions.act_window_close'}
