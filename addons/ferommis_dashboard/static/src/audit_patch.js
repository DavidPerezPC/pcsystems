import { _t } from "@web/core/l10n/translation";
import * as spreadsheet from "@odoo/o-spreadsheet";
import { parseAccountingDate } from "@spreadsheet_account/accounting_functions";
import { camelToSnakeObject } from "@spreadsheet/helpers/helpers";

const { cellMenuRegistry, clickableCellRegistry } = spreadsheet.registries;
const { astToFormula } = spreadsheet;
const {
    isEvaluationError,
    toString,
    toBoolean,
    getFunctionsFromTokens,
} = spreadsheet.helpers;

const AUDITABLE_FUNCTIONS = [
    "ODOO.BALANCE",
    "ODOO.CREDIT",
    "ODOO.DEBIT",
    "ODOO.RESIDUAL",
    "ODOO.PARTNER.BALANCE",
    "ODOO.BALANCE.TAG",
    "ODOO.BALANCE.FERROMMIS",
    "ODOO.RESIDUAL.FERROMMIS",
];

function getFirstAuditableFunction(tokens) {
    return getFunctionsFromTokens(tokens, AUDITABLE_FUNCTIONS)[0];
}

function getNumberOfAuditableFormulas(tokens) {
    return getFunctionsFromTokens(tokens, AUDITABLE_FUNCTIONS).length;
}

function splitCsv(arg) {
    if (!arg || arg.value === undefined || arg.value === null) {
        return [];
    }
    if (isEvaluationError(arg.value)) {
        return [];
    }
    return toString(arg.value)
        .split(",")
        .map((v) => v.trim())
        .filter(Boolean);
}

function buildAuditAction(env, position) {
    const sheetId = position.sheetId;
    const cell = env.model.getters.getCell(position);
    const func = getFirstAuditableFunction(cell.compiledFormula.tokens);
    if (!func) {
        return null;
    }

    let codes;
    let partner_ids;
    let account_tag_ids;
    let journal_ids;
    let journal_types;
    let partner_category_names;
    let date_range;
    let offset;
    let companyIdArg;
    let includeUnpostedArg;

    const parsed_args = func.args
        .map(astToFormula)
        .map((arg) => env.model.getters.evaluateFormulaResult(sheetId, arg));

    if (func.functionName === "ODOO.PARTNER.BALANCE") {
        [partner_ids, codes, date_range, offset, companyIdArg, includeUnpostedArg] =
            parsed_args;
    } else if (func.functionName === "ODOO.BALANCE.TAG") {
        [account_tag_ids, date_range, offset, companyIdArg, includeUnpostedArg] =
            parsed_args;
    } else if (
        func.functionName === "ODOO.BALANCE.FERROMMIS" ||
        func.functionName === "ODOO.RESIDUAL.FERROMMIS"
    ) {
        [
            codes,
            date_range,
            journal_ids,
            journal_types,
            partner_category_names,
            offset,
            companyIdArg,
            includeUnpostedArg,
        ] = parsed_args;
    } else {
        [codes, date_range, offset, companyIdArg, includeUnpostedArg] = parsed_args;
    }

    const codesList = splitCsv(codes);
    const locale = env.model.getters.getLocale();
    let dateRange;
    if (date_range?.value && !isEvaluationError(date_range.value)) {
        dateRange = parseAccountingDate(date_range, locale);
    } else if (
        ["ODOO.PARTNER.BALANCE", "ODOO.RESIDUAL", "ODOO.BALANCE.TAG"].includes(
            func.functionName
        )
    ) {
        dateRange = parseAccountingDate({ value: new Date().getFullYear() }, locale);
    }
    const offsetNumber = parseInt(offset?.value) || 0;
    if (dateRange) {
        dateRange.year += offsetNumber;
    }
    const companyId = parseInt(companyIdArg?.value) || null;
    let includeUnposted = false;
    try {
        includeUnposted = toBoolean(includeUnpostedArg?.value);
    } catch {
        includeUnposted = false;
    }

    let param;
    if (func.functionName === "ODOO.BALANCE.TAG") {
        const accountTagIds = splitCsv(account_tag_ids);
        param = [
            camelToSnakeObject({
                accountTagIds,
                dateRange,
                companyId,
                includeUnposted,
            }),
        ];
    } else if (func.functionName === "ODOO.PARTNER.BALANCE") {
        const partnerIds = splitCsv(partner_ids);
        param = [
            camelToSnakeObject({
                dateRange,
                companyId,
                codes: codesList,
                includeUnposted,
                partnerIds,
            }),
        ];
    } else if (
        func.functionName === "ODOO.BALANCE.FERROMMIS" ||
        func.functionName === "ODOO.RESIDUAL.FERROMMIS"
    ) {
        const journalIds = splitCsv(journal_ids);
        const journalTypes = splitCsv(journal_types);
        const partnerCategoryNames = splitCsv(partner_category_names);
        param = [
            camelToSnakeObject({
                dateRange,
                companyId,
                codes: codesList,
                includeUnposted,
                journalIds,
                journalTypes,
                partnerCategoryNames,
            }),
        ];
    } else {
        param = [
            camelToSnakeObject({
                dateRange,
                companyId,
                codes: codesList,
                includeUnposted,
            }),
        ];
    }

    return param;
}

async function executeAudit(env, position, newWindow) {
    const param = buildAuditAction(env, position);
    if (!param) {
        return;
    }
    const action = await env.services.orm.call(
        "account.account",
        "spreadsheet_move_line_action",
        param
    );
    await env.services.action.doAction(action, { newWindow });
}

function isAuditablePosition(env, position) {
    const evaluatedCell = env.model.getters.getEvaluatedCell(position);
    const cell = env.model.getters.getCell(position);
    return (
        !isEvaluationError(evaluatedCell.value) &&
        evaluatedCell.value !== "" &&
        cell &&
        cell.isFormula &&
        getNumberOfAuditableFormulas(cell.compiledFormula.tokens) === 1
    );
}

// Right-click "See records" menu — replace native entry so it also handles
// ODOO.BALANCE.FERROMMIS and is available in read-only/dashboard mode.
cellMenuRegistry.replace("move_lines_see_records", {
    name: _t("See records"),
    sequence: 176,
    isReadonlyAllowed: true,
    async execute(env, newWindow) {
        const position = env.model.getters.getActivePosition();
        await executeAudit(env, position, newWindow);
    },
    isVisible: (env) => {
        const position = env.model.getters.getActivePosition();
        return isAuditablePosition(env, position);
    },
    icon: "o-spreadsheet-Icon.SEE_RECORDS",
});

// In dashboard (read-only) mode the cell menu is bypassed for direct clicks.
// Register a clickableCellRegistry entry so single-click on a cell containing
// an audit-eligible accounting formula opens the filtered list — passing
// journal_ids / partner_category_names for ODOO.BALANCE.FERROMMIS.
clickableCellRegistry.add("move_lines_see_records", {
    condition: (position, getters) =>
        isAuditablePosition({ model: { getters } }, position),
    execute: (position, env) => executeAudit(env, position, false),
    title: () => _t("See records"),
    sequence: 6,
});
