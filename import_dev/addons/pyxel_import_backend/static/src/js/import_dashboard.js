/** @odoo-module **/
import { Component, useState, onMounted } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

class ImportDashboard extends Component {
    static template = "pyxel_import_backend.ImportDashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ data: null, loading: true, error: null });
        onMounted(() => this.loadData());
    }

    async loadData() {
        try {
            // Los params de una ir.actions.client NO llegan como prop directo:
            // el action service los mete dentro de props.action.params
            // (ver _getActionInfo en action_service.js: props = {...props, action}).
            // Se guarda en la instancia (no solo local aqui) porque openList,
            // openExtraidos y exportPdf tambien lo necesitan, y se llaman
            // fuera de loadData.
            this.ventaEnetecOnly = (this.props.action && this.props.action.params
                && this.props.action.params.ventaEnetecOnly) || false;
            const data = await this.orm.call("importation.load", "get_dashboard_data", [], {
                venta_enetec_only: this.ventaEnetecOnly,
            });
            Object.assign(this.state, { data, loading: false });
        } catch (e) {
            this.state.loading = false;
            this.state.error = e.message || "Error cargando datos";
        }
    }

    async refresh() {
        this.state.loading = true;
        await this.loadData();
    }

    async exportPdf() {
        await this.action.doAction({
            type: "ir.actions.report",
            report_name: "pyxel_import_backend.report_import_dashboard_template",
            report_type: "qweb-pdf",
            report_file: "pyxel_import_backend.report_import_dashboard_template",
            name: "Tablero de Importación",
            data: { venta_enetec_only: this.ventaEnetecOnly },
        });
    }

    // Mismo filtro que usa el servidor en get_dashboard_data (customer_id.name
    // empieza por "VENTA ENETEC"). Se antepone al dominio de cada lista para
    // que el detalle no muestre mas que el resumen de arriba. Solo aplica a
    // las listas de importation.load -- CUPET y Comercial/Leads quedan sin
    // filtrar a proposito, no son del cliente VENTA ENETEC.
    ventaDomain() {
        return this.ventaEnetecOnly ? [
            "|",
            ["customer_id.name", "like", "VENTA ENETEC%"],
            ["importation_id.comercial_id.name", "ilike", "Gabriela"],
        ] : [];
    }

    /** Primer y último día del mes "YYYY-MM", como los espera el dominio. */
    rangoMes(mes) {
        const [y, m] = mes.split("-").map(Number);
        const lastDay = new Date(y, m, 0).getDate();
        return [`${mes}-01`, `${mes}-${String(lastDay).padStart(2, "0")}`];
    }

    openHuerfanosMes(mes) {
        const [from, to] = this.rangoMes(mes);
        this.openList(
            [["importation_id", "=", false], ["arrival_date", ">=", from], ["arrival_date", "<=", to]],
            "Huérfanos " + mes
        );
    }

    openExtraidosMes(mes) {
        const [from, to] = this.rangoMes(mes);
        this.openList(
            [["extraction_date", ">=", from], ["extraction_date", "<=", to]],
            "Extraídos " + mes
        );
    }

    openPendientesMes(mes) {
        const [from, to] = this.rangoMes(mes);
        this.openList(
            [["extraction_date", "=", false], ["arrival_date", ">=", from], ["arrival_date", "<=", to]],
            "Pendientes de extraer " + mes
        );
    }

    openDelDia(fila, columna) {
        const bloque = fila === "hab" ? this.state.data.del_dia_hab
                                      : this.state.data.del_dia_ext;
        const ids = (bloque.ids || {})[columna] || [];
        if (!ids.length) { return; }
        const fecha = fila === "hab" ? this.state.data.fecha_habilitacion
                                     : this.state.data.fecha_extraccion;
        const queFila = fila === "hab" ? "Habilitados" : "Extraídos";
        const queCol = columna === "total" ? "" : " · " + columna;
        this.openList([["id", "in", ids]], `${queFila} ${fecha}${queCol}`);
    }

    openList(domain, name) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: name || "Contenedores",
            res_model: "importation.load",
            view_mode: "list,form",
            views: [[false, "list"], [false, "form"]],
            domain: [...this.ventaDomain(), ...domain],
        });
    }

    get agingBars() {
        const d = this.state.data;
        if (!d) return [];
        const total = d.aging.total;
        return [
            { label: "0–4 días", key: "de_0_4", color: "#28a745", days_from: 0, days_to: 4 },
            { label: "5–9 días", key: "de_5_9", color: "#ffc107", days_from: 5, days_to: 9 },
            { label: "10–19 días", key: "de_10_19", color: "#fd7e14", days_from: 10, days_to: 19 },
            { label: "20–29 días", key: "de_20_29", color: "#dc3545", days_from: 20, days_to: 29 },
            { label: "+30 días", key: "de_30_mas", color: "#6f42c1", days_from: 30, days_to: 9999 },
        ].map(b => ({
            ...b,
            count: d.aging[b.key],
            pct: Math.round((d.aging[b.key] / total) * 100),
        }));
    }

    domainForAging(b) {
        const today = new Date();
        const fmt = (d) => d.toISOString().split("T")[0];
        const base = [["extraction_date", "=", false], ["arrival_date", "!=", false]];
        if (b.days_to >= 9999) {
            // El servidor corta esta franja en (days_from - 1), no en days_from
            // (mismo patrón de límites que las franjas anteriores: el corte de
            // "+30 días" es el mismo que el límite superior de "20-29 días").
            const d = new Date(today); d.setDate(d.getDate() - (b.days_from - 1));
            return [...base, ["arrival_date", "<", fmt(d)]];
        }
        const from = new Date(today); from.setDate(from.getDate() - b.days_to);
        const to = new Date(today); to.setDate(to.getDate() - b.days_from);
        return [...base, ["arrival_date", ">=", fmt(from)], ["arrival_date", "<=", fmt(to)]];
    }

    formatDate(ds) {
        if (!ds) return "—";
        // Parsear la cadena ISO directamente para evitar la conversion UTC->local
        // que correria la fecha un dia atras en zonas con UTC offset negativo.
        const parts = ds.split('-');
        if (parts.length === 3) return `${parts[2].padStart(2,'0')}/${parts[1].padStart(2,'0')}/${parts[0]}`;
        return ds;
    }

    openHistoricoMes(mes) {
        // mes = "YYYY-MM", calcular primer y último día real del mes
        const [y, m] = mes.split("-").map(Number);
        const from = `${mes}-01`;
        const lastDay = new Date(y, m, 0).getDate(); // día 0 del mes siguiente = último del actual
        const to = `${mes}-${String(lastDay).padStart(2, "0")}`;
        this.openList(
            [["extraction_date", ">=", from], ["extraction_date", "<=", to]],
            mes
        );
    }

    openExtraidos() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Extraídos (" + this.state.data.fecha_extraccion + ")",
            res_model: "importation.load",
            view_mode: "list,form",
            views: [[this.state.data.view_extraidos_id, "list"], [false, "form"]],
            domain: [...this.ventaDomain(), ["extraction_date", "=", this.state.data.fecha_extraccion]],
        });
    }

    openCupetExtraidos() {
        this.action.doAction("pyxel_import_backend.action_importation_load_cupet_extraidos");
    }

    openCupetPendientes() {
        this.action.doAction("pyxel_import_backend.action_importation_load_cupet_pendientes");
    }

    fmtNum(n) {
        if (n === null || n === undefined || isNaN(n)) return "—";
        return Number(n).toLocaleString("es-ES", { maximumFractionDigits: 2 });
    }

    openLeads(role, bucket, title) {
        const key = role === "client" ? "clientes" : "proveedores";
        const c = this.state.data.comercial[key];
        const domain = [["active", "=", true], ["en_party_role", "=", role]];
        if (bucket === "acreditados") {
            domain.push(["partner_id.is_accredited", "=", true]);
        } else if (bucket === "en_aprobacion") {
            domain.push(["partner_id.is_accredited", "=", false]);
            if (c.stages_en_aprobacion.length) {
                domain.push(["stage_id", "in", c.stages_en_aprobacion]);
            }
        } else {
            domain.push(["partner_id.is_accredited", "=", false]);
            if (c.stages_potenciales.length) {
                domain.push(["stage_id", "in", c.stages_potenciales]);
            }
        }
        this.action.doAction({
            type: "ir.actions.act_window",
            name: title,
            res_model: "crm.lead",
            view_mode: "kanban,list,form",
            views: [[false, "kanban"], [false, "list"], [false, "form"]],
            domain: domain,
        });
    }
}

registry.category("actions").add("import_dashboard", ImportDashboard);
