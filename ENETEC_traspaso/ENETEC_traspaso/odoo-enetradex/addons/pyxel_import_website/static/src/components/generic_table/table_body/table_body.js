/** @odoo-module **/
import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
console.log("TableBody");
export class TableBody extends Component {
  static template = "childcare_management.TableBodyTemplate";
  static props = {
    rows: Array,
    columns: Array,
  };

  formatCell(value, formatFn) {
    return formatFn ? formatFn(value) : value;
  }
}
registry
  .category("public_components")
  .add("childcare_management.TableBody", TableBody);
