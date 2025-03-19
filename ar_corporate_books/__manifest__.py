# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Argentine Corporate and Accounting Books',
    'version': '1.0',
    'category': 'Accounting/Localization/Argentina',
    'summary': 'Manage corporate and accounting books according to Argentine regulations',
    'description': """
Argentine Corporate and Accounting Books Management
===================================================
This module allows companies to:
- Manage corporate books (libros societarios)
- Manage accounting books according to Argentine regulations
- Control book inventory
- Create and manage meeting minutes
- Maintain shareholder registry
- Track assembly attendance
- Generate officia l reports
""",
    'author': 'Odoo',
    'website': 'https://www.odoo.com',
    'depends': [
        'base',
        'account',
        'contacts',
        'l10n_ar',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/corporate_book_views.xml',
        'views/accounting_book_views.xml',
        'views/book_inventory_views.xml',
        'views/meeting_minute_views.xml',
        'views/shareholder_views.xml',
        'views/assembly_attendance_views.xml',
        'views/wizard_views.xml',
        'views/menu_views.xml',
        'report/report.xml',
        'report/corporate_book_report.xml',
        'report/accounting_book_report.xml',
        'report/meeting_minute_report.xml',
        'report/shareholder_report.xml',
        'report/assembly_attendance_report.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'OEEL-1',
}
