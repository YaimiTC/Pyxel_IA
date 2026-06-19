import requests
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class TransportHub(models.Model):
    _name = 'transport.hub'
    _description = 'Ports and Airports'

    name = fields.Char(string='Name')
    country_id = fields.Many2one(comodel_name='res.country')
    hub_type = fields.Selection(selection=[
        ('Port', 'Port'),
        ('Airport', 'Airport')
    ])
    code = fields.Char(string="Local Code")
    icao_code = fields.Char(string='ICAO Code')
    iata_code = fields.Char(string='IATA Code')
    un_locode = fields.Char(string='UN/LOCODE')
    latitude = fields.Float(string='Latitude', digits=(16, 6))
    longitude = fields.Float(string='Longitude', digits=(16, 6))

    def open_google_maps(self):
        self.ensure_one()
        if self.latitude and self.longitude:
            return {
                'type': 'ir.actions.act_url',
                'url': f'https://www.google.com/maps/search/?api=1&query={self.latitude},{self.longitude}',
                'target': 'new'
            }
        else:
            raise UserError(_("Incomplete coordinates: unable to open in Google Maps."))

    @api.model
    def _sync_airports_from_api(self):
        url = "https://airportsapi.com/api/airports?page[size]=100&include=country"
        headers = {"Accept": "application/json"}

        while url:
            try:
                res = requests.get(url, headers=headers, timeout=10)
                if res.status_code != 200:
                    break
                payload = res.json()
            except Exception as e:
                break

            for airport in payload.get("data", []):
                attrs = airport.get("attributes", {})
                rels = airport.get("relationships", {})
                country_data = rels.get("country", {}).get("data", {})
                country_code = country_data.get("id")
                country = self.env["res.country"].search([("code", "=", country_code)], limit=1)
                if not country:
                    continue

                code = attrs.get("local_code") or attrs.get("code")
                if not code:
                    continue

                vals = {
                    "name": attrs.get("name"),
                    "code": code,
                    "iata_code": attrs.get("iata_code") or False,
                    "icao_code": attrs.get("icao_code") or False,
                    "latitude": float(attrs.get("latitude", "0.0")),
                    "longitude": float(attrs.get("longitude", "0.0")),
                    "hub_type": "Airport",
                    "country_id": country.id,
                }

                existing = self.search([("code", "=", code)], limit=1)
                if existing:
                    existing.write(vals)
                else:
                    self.create(vals)

            url = payload.get("links", {}).get("next")
