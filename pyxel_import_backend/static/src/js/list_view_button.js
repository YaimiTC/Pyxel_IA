/** @odoo-module **/
import { ListController } from "@web/views/list/list_controller";
import { listView } from "@web/views/list/list_view";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, useState } from "@odoo/owl";

export class PurchaseProviderEvaluationTreeComponent extends Component {
    setup() {
          this.orm = useService("orm");
          this.action = useService("action");

        }

 };

export class PurchaseProviderEvaluationTreeController extends ListController {
 setup() {
    super.setup();
    this.buttons_template = 'purchase_provider_evaluation_buttons';
    this.orm = useService("orm");
    this.action = useService("action");
  }

     onClickPurchaseProviderEvaluation(){
        const activeId = this.props.context.active_id;

        console.log("!!!! active_id",activeId);
        return this.action.doAction({
                type: "ir.actions.act_window",
                name: "Nueva Evaluación",
                res_model: "wizard.evaluate.providers",
                view_mode: "form",
                views: [[false, "form"]],
                target: "new",
                context: {
                    default_sale_order_id: parseInt(activeId),
                }
    });


     }
};

PurchaseProviderEvaluationTreeController.components = {
    ...ListController.components,
    PurchaseProviderEvaluationTreeComponent,
};


registry.category("views").add('custom_provider_eval_tree',
{  ...listView,
    buttonTemplate: 'purchase_provider_evaluation_buttons',
    Controller: PurchaseProviderEvaluationTreeController,

    });
