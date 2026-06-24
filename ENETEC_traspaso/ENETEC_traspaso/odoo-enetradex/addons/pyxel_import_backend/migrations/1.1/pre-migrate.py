def migrate(cr, version):
    cr.execute("""
        ALTER TABLE sale_order
        ADD COLUMN IF NOT EXISTS is_cost_order boolean DEFAULT false;
    """)
