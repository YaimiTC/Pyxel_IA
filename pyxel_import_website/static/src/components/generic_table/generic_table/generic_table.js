/** @odoo-module **/
import { Component, onMounted, onWillUnmount, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { TableBody } from "../table_body/table_body";
import { TableBodyMobile } from "../table_body_mobile/table_body_mobile";
import { TablePagination } from "../table_pagination/table_pagination";

console.log("GenericTable");
export class GenericTable extends Component {
  static template = "childcare_management.MainTemplate";
  static components = { TableBody, TableBodyMobile, TablePagination };
  static props = {
    columns: { type: Array },
    rows: { type: Array },
    initialPageSize: { type: Number, optional: true },
  };

  setup() {
    this.state = useState({
      sortedColumn: null,
      sortDirection: "asc",
      currentPage: 0,
      pageSize: this.props.initialPageSize || 10,
      isMobile: window.innerWidth <= 768,
    });
    this.handleSort = this.handleSort.bind(this);

    this.checkMobile = () => {
      this.state.isMobile = window.innerWidth <= 768;
    };
    onMounted(() => {
      window.addEventListener("resize", this.checkMobile);
    });

    onWillUnmount(() => {
      window.removeEventListener("resize", this.checkMobile);
    });
  }
  // Ordenamiento
  handleSort(columnName) {
    const column = this.props.columns.find((col) => col.name === columnName);
    if (!column?.isSortable) return;

    if (this.state.sortedColumn === columnName) {
      this.state.sortDirection =
        this.state.sortDirection === "asc" ? "desc" : "asc";
    } else {
      this.state.sortedColumn = columnName;
      this.state.sortDirection = "asc";
    }
    this.state.currentPage = 0;
  }

  // Datos procesados
  get processedData() {
    let data = [...this.props.rows];
    const sortedColumn = this.props.columns.find(
      (col) => col.name === this.state.sortedColumn
    );

    if (sortedColumn?.isSortable && this.state.sortedColumn) {
      data.sort((a, b) => {
        const valA = a[this.state.sortedColumn];
        const valB = b[this.state.sortedColumn];
        const direction = this.state.sortDirection === "asc" ? 1 : -1;

        // Mejorar comparación numérica/string
        if (typeof valA === "number" && typeof valB === "number") {
          return (valA - valB) * direction;
        }
        return (
          String(valA).localeCompare(String(valB), { numeric: true }) *
          direction
        );
      });
    }

    return data;
  }

  // Datos paginados
  get paginatedData() {
    const start = this.state.currentPage * this.state.pageSize;
    return this.processedData.slice(start, start + this.state.pageSize);
  }

  // Total de páginas
  get totalPages() {
    return Math.ceil(this.processedData.length / this.state.pageSize);
  }

  // Manejar cambio de página
  handlePageChange = (newPage) => {
    this.state.currentPage = Math.max(
      0,
      Math.min(newPage, this.totalPages - 1)
    );
  };

  handlePageSizeChange = (newSize) => {
    this.state.pageSize = newSize;
    this.state.currentPage = 0;
  };
}

registry
  .category("public_components")
  .add("childcare_management.GenericTable", GenericTable);
