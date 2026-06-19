/** @odoo-module **/
import { Component, markup, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { GenericTable } from "../generic_table/generic_table/generic_table";

export class ImportationsTable extends Component {
  static template = "pyxel_import_website.ImportationsTableTemplate";
  static components = {
    GenericTable,
  };

  setup() {
    this.orm = useService("orm");
    this.rpc = useService("rpc");

    this.state = useState({
      records: [],
      filteredData: [],
      filters: {
        global: "",
      },
      isLoading: false,
    });

    this.columns = [
      {
        name: "name",
        header: "Número",
        sortable: true,
        cell: (v, row) =>
          markup(`<a href="/importations/view/${row.id}" style="text-decoration: none;">${v}</a>`),
      },
      {
        name: "provider",
        header: "Proveedor",
        sortable: true,
      },
      {
        name: "customer",
        header: "Cliente",
        sortable: true,
      },
      {
        name: "bl",
        header: "BL",
        sortable: true,
      },
      {
        name: "stage",
        header: "Estado",
        sortable: true,
      },
    ];

    onWillStart(this._loadImportations.bind(this));
    this.updateFilter = this.updateFilter.bind(this);
  }

    async _loadImportations() {
      this.state.isLoading = true;
      try {
        const user = await this.rpc("/api/user-data", {});
        const partnerId = user.data.user.partner_id;
        const isPortal = user.data.user.is_portal;

        let domain = [];

        if (isPortal) {
          console.log("Usuario de Portal");
          // Leer el partner base
          const partnerData = await this.orm.read("res.partner", [partnerId], ["parent_id"]);
          const companyPartnerId = partnerData[0]?.parent_id?.[0] || partnerId;

          // Leer el tipo de contacto desde la empresa
          const companyData = await this.orm.read("res.partner", [companyPartnerId], ["contact_type_id"]);
          const contactTypeId = companyData[0]?.contact_type_id?.[0];

          let typeOfContact = null;

          if (contactTypeId) {
            const contactTypeData = await this.orm.read("res.partner.contact.type", [contactTypeId], ["type_of_contact"]);
            typeOfContact = contactTypeData[0]?.type_of_contact;
            console.log("Tipo de contacto tiene como valor:", typeOfContact);
          }

          // Aplicar dominio según tipo
          switch (typeOfContact) {
            case "Supplier":
              domain = [["provider_id", "=", companyPartnerId]];
              break;
            case "Client":
              domain = [["customer_id", "=", companyPartnerId]];
              break;
            default:
              domain=[["id", "=", false]]
              console.log("Tipo de contacto no reconocido o no definido:", typeOfContact);
          }
        }

        const records = await this.orm.searchRead(
          "importation.process",
          domain,
          ["name", "provider_id", "customer_id", "purchase_condition_number", "stage_id"]
        );

        this.state.records = records.map((r) => ({
          id: r.id,
          name: r.name,
          provider: r.provider_id?.[1],
          customer: r.customer_id?.[1],
          bl: r.purchase_condition_number || "—",
          stage: r.stage_id?.[1],
        }));

        this.state.filteredData = [...this.state.records];
      } catch (error) {
        console.error("Error loading importations:", error);
      } finally {
        this.state.isLoading = false;
      }
    }


  updateFilter(filterType, value) {
    this.state.filters[filterType] = value;
    this.applyFilters();
  }

  applyFilters() {
    this.state.filteredData = this.state.records.filter((record) => {
      return Object.entries(this.state.filters).every(([key, filterValue]) => {
        if (!filterValue) return true;
        return this.columns.some((col) =>
          String(record[col.name] || "")
            .toLowerCase()
            .includes(filterValue.toLowerCase())
        );
      });
    });
  }
}

registry
  .category("public_components")
  .add("pyxel_import_website.ImportationsTable", ImportationsTable);
