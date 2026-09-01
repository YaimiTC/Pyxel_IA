DTCC_XML_IDS = [
    'importation_destination_pinar_del_rio',
    'importation_destination_artemisa',
    'importation_destination_la_habana',
    'importation_destination_mayabeque',
    'importation_destination_matanzas',
    'importation_destination_cienfuegos',
    'importation_destination_villa_clara',
    'importation_destination_sancti_spiritus',
    'importation_destination_ciego_de_avila',
    'importation_destination_camaguey',
    'importation_destination_las_tunas',
    'importation_destination_holguin',
    'importation_destination_granma',
    'importation_destination_santiago_de_cuba',
    'importation_destination_guantanamo',
    'importation_destination_isla_juventud',
]

DTCC_NAMES = [
    'DTCC Pinar del Río', 'DTCC Artemisa', 'DTCC La Habana',
    'DTCC Mayabeque', 'DTCC Matanzas', 'DTCC Cienfuegos',
    'DTCC Villa Clara', 'DTCC Sancti Spíritus', 'DTCC Ciego de Ávila',
    'DTCC Camagüey', 'DTCC Las Tunas', 'DTCC Holguín',
    'DTCC Granma', 'DTCC Santiago de Cuba', 'DTCC Guantánamo',
    'DTCC Isla de la Juventud',
]


def migrate(cr, version):
    # Los "DTCC <provincia>" eran destinos de prueba (uno por provincia).
    # Llego el nomenclador oficial SIOC (48 destinos reales, ver
    # data/importation_destination_data.xml) y entre ellos hay uno que
    # tambien se llama "DTCC Cienfuegos" (external_id 01079D004) -- si este
    # borrado corre despues de que se cargue ese archivo (post-migrate),
    # el unique(name) choca contra el de prueba que sigue ahi. Por eso va
    # en pre-migrate: corre antes de que el modulo cargue sus datos.
    #
    # El unico contenedor real que usaba "DTCC La Habana" (1) queda con el
    # destino en blanco -- el FK es ON DELETE SET NULL -- a la espera de
    # que alguien le ponga el destino real del nomenclador nuevo.
    cr.execute(
        "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'importation_destination')"
    )
    if not cr.fetchone()[0]:
        return
    cr.execute(
        "DELETE FROM importation_destination WHERE name = ANY(%s)",
        (DTCC_NAMES,)
    )
    cr.execute(
        """
        DELETE FROM ir_model_data
        WHERE module = 'pyxel_import_backend'
          AND model = 'importation.destination'
          AND name = ANY(%s)
        """,
        (DTCC_XML_IDS,)
    )
