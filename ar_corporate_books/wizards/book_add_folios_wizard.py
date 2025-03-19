# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class BookAddFoliosWizard(models.TransientModel):
    _name = 'ar.book.add.folios.wizard'
    _description = 'Add Folios to Book'

    book_id = fields.Many2one('ar.corporate.book', string='Book', required=True, readonly=True)
    current_folios = fields.Integer(string='Current Folios Used', readonly=True)
    folios_to_add = fields.Integer(string='Folios to Add', required=True, default=1)
    reason = fields.Text(string='Reason', required=True)
    date = fields.Date(string='Date', default=fields.Date.context_today, required=True)

    @api.constrains('folios_to_add')
    def _check_folios_to_add(self):
        for wizard in self:
            if wizard.folios_to_add <= 0:
                raise ValidationError(_("The number of folios to add must be greater than 0."))
            
            if wizard.current_folios + wizard.folios_to_add > wizard.book_id.folios:
                raise ValidationError(_("Cannot exceed the total number of folios in the book (%s).", wizard.book_id.folios))

    def action_add_folios(self):
        self.ensure_one()
        
        # Update folios used in the book
        new_folios_used = self.current_folios + self.folios_to_add
        self.book_id.write({
            'folios_used': new_folios_used,
        })
        
        # Log the action in the chatter
        msg = _(
            "Added %s folios to the book (from %s to %s).<br/>"
            "Reason: %s<br/>"
            "Date: %s"
        ) % (
            self.folios_to_add,
            self.current_folios,
            new_folios_used,
            self.reason,
            self.date
        )
        self.book_id.message_post(body=msg)
        
        return {'type': 'ir.actions.act_window_close'}
