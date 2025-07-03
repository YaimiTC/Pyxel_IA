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
      console.log(isPortal)
      let domain = [];

      if (isPortal) {
        const contactData = await this.orm.read("res.partner", [partnerId], ["contact_type_id"]);
        const contactType = contactData[0]?.contact_type_id?.[1];

        if (contactType === "Supplier") {
          domain = [["provider_id", "=", partnerId]];
        } else if (contactType === "Client") {
          domain = [["customer_id", "=", partnerId]];
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
        bl: r.purchase_condition_number,
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
