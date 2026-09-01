# -*- coding: utf-8 -*-

def post_init_hook(env):
    """Solo cubre la instalacion nueva del modulo; para -u de un modulo
    ya instalado, el mismo sembrado corre por el <function> de
    data/importation_importer_data.xml."""
    env['importation.importer']._seed_tcm_match_names()
