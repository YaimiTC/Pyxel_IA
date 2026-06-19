/** @odoo-module **/
import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
console.log("TablePagination");
export class TablePagination extends Component {
  static template = "childcare_management.TablePaginationTemplate";
  static props = {
    currentPage: Number,
    totalPages: Number,
    pageSize: Number,
    onPageChange: Function,
    onPageSizeChange: Function,
  };

  get pageOptions() {
    return [10, 20, 50, 100];
  }

  get visiblePages() {
    const maxVisible = 5;
    const start = Math.max(
      0,
      this.props.currentPage - Math.floor(maxVisible / 2)
    );
    return Array.from(
      { length: Math.min(maxVisible, this.props.totalPages - start) },
      (_, i) => start + i
    );
  }
  onChangePageSize(ev) {
    const newSize = parseInt(ev.target.value);
    this.props.onPageSizeChange(newSize);
  }

  onChangePage(page) {
    this.props.onPageChange(page);
  }
}
registry
  .category("public_components")
  .add("childcare_management.TablePagination", TablePagination);
