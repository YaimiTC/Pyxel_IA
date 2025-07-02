/** @odoo-module **/
import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
console.log("TableBodyMobile");
export class TableBodyMobile extends Component {
  static template = "childcare_management.TableBodyMobileTemplate";
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
  .add("childcare_management.TableBodyMobile", TableBodyMobile);
