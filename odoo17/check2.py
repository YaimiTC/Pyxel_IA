import os
base = r"D:\trabajo\Pyxel\IA\odoo17\proyectos"
local_mods = set()
for repo in os.listdir(base):
    rp = os.path.join(base, repo)
    if os.path.isdir(rp):
        for mod in os.listdir(rp):
            if os.path.exists(os.path.join(rp, mod, "__manifest__.py")):
                local_mods.add(mod)
backup = ["accounting_pdf_reports","bcc_api_gateway","bcc_currency_sync","l10n_cu","l10n_cu_address","l10n_cu_banks","l10n_cu_hr","l10n_cu_hr_contract","l10n_cu_hr_holidays","l10n_cu_hr_payroll","l10n_cu_hr_payroll_account","l10n_cu_hr_payroll_submayor","l10n_cu_reports","l10n_mt_pos","om_hr_payroll","om_hr_payroll_account","pyxel_account_invoice_report","pyxel_ceimpex_integration","pyxel_cem_configuration","pyxel_cem_delivery_methods","pyxel_cem_import","pyxel_cem_sale","pyxel_cem_sale_format","pyxel_cem_seller_payment","pyxel_cem_virtual_contract","pyxel_cem_website_account","pyxel_cem_website_sale","pyxel_custom_invoice_format","pyxel_import_backend","pyxel_import_conciliation_report","pyxel_import_email_excel","pyxel_import_website","pyxel_inventory_report_albaran","pyxel_inventory_terms_correction","pyxel_link_payment_tropipay","pyxel_multi_currency_payment_in_pos","pyxel_odin2_online_user_manuals","pyxel_phone_signup_signin","pyxel_stock_ONEI","pyxel_stock_report_certification","pyxel_stock_tarjetaestiba","pyxel_stock_translate","report_xlsx","theme_scita","transport_hub"]
missing = [m for m in backup if m not in local_mods]
print(f"Faltan ({len(missing)}):")
[print(f"  x {m}") for m in sorted(missing)]
print(f"Cubiertos: {len(backup)-len(missing)}/{len(backup)}")

