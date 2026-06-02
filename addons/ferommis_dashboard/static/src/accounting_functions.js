import { _t } from "@web/core/l10n/translation";
import * as spreadsheet from "@odoo/o-spreadsheet";
import { parseAccountingDate } from "@spreadsheet_account/accounting_functions";

const { functionRegistry } = spreadsheet.registries;
const { arg, toBoolean, toString, toNumber } = spreadsheet.helpers;

function splitCsv(arg) {
    return toString(arg?.value || "")
        .split(",")
        .map((v) => v.trim())
        .filter(Boolean);
}

functionRegistry.add("ODOO.RESIDUAL.FERROMMIS", {
    description: _t(
        "Residual amount filtered by accounts, journals and partner categories (FEROMMIS)."
    ),
    args: [
        arg("account_codes (string)", _t("The prefix of the accounts (comma-separated).")),
        arg(
            "date_range (string, date)",
            _t(`The date range. Supported formats are "21/12/2022", "Q1/2022", "12/2022", and "2022".`)
        ),
        arg("journal_ids (string, optional)", _t("Journal ids to include (comma-separated).")),
        arg("journal_types (string, optional)", _t("Journal types (sale, purchase, ...). Comma-separated.")),
        arg("partner_categories (string, optional)", _t("Partner category names (comma-separated).")),
        arg("offset (number, default=0)", _t("Offset applied to the year.")),
        arg("company_id (number, optional)", _t("The company to target (Advanced).")),
        arg(
            "include_unposted (boolean, default=FALSE)",
            _t("Set to TRUE to include unposted entries.")
        ),
    ],
    category: "Odoo",
    returns: ["NUMBER"],
    compute: function (
        accountCodes,
        dateRange,
        journalIds = { value: "" },
        journalTypes = { value: "" },
        partnerCategoryNames = { value: "" },
        offset = { value: 0 },
        companyId = { value: null },
        includeUnposted = { value: false }
    ) {
        const _codes = splitCsv(accountCodes).sort();
        const _journalIds = splitCsv(journalIds);
        const _journalTypes = splitCsv(journalTypes);
        const _partnerCategoryNames = splitCsv(partnerCategoryNames);
        const _offset = toNumber(offset, this.locale);
        const _dateRange = parseAccountingDate(dateRange, this.locale);
        const _companyId = companyId?.value ?? null;
        let _includeUnposted = false;
        try {
            _includeUnposted = toBoolean(includeUnposted);
        } catch {
            _includeUnposted = false;
        }
        const value = this.getters.getFerommisFilteredResidual(
            _codes,
            _dateRange,
            _journalIds,
            _journalTypes,
            _partnerCategoryNames,
            _offset,
            _companyId,
            _includeUnposted
        );
        return {
            value,
            format: this.getters.getCompanyCurrencyFormat(_companyId) || "#,##0.00",
        };
    },
});

functionRegistry.add("ODOO.BALANCE.FERROMMIS", {
    description: _t(
        "Balance filtered by accounts, journals, journal types, and partner categories (FEROMMIS)."
    ),
    args: [
        arg(
            "account_codes (string)",
            _t("The prefix of the accounts (comma-separated).")
        ),
        arg(
            "date_range (string, date)",
            _t(`The date range. Supported formats are "21/12/2022", "Q1/2022", "12/2022", and "2022".`)
        ),
        arg(
            "journal_ids (string, optional)",
            _t("Journal ids to include (comma-separated).")
        ),
        arg(
            "journal_types (string, optional)",
            _t("Journal types to include (sale, purchase, cash, bank, general). Comma-separated.")
        ),
        arg(
            "partner_categories (string, optional)",
            _t("Partner category names to include (comma-separated).")
        ),
        arg("offset (number, default=0)", _t("Offset applied to the year.")),
        arg("company_id (number, optional)", _t("The company to target (Advanced).")),
        arg(
            "include_unposted (boolean, default=FALSE)",
            _t("Set to TRUE to include unposted entries.")
        ),
    ],
    category: "Odoo",
    returns: ["NUMBER"],
    compute: function (
        accountCodes,
        dateRange,
        journalIds = { value: "" },
        journalTypes = { value: "" },
        partnerCategoryNames = { value: "" },
        offset = { value: 0 },
        companyId = { value: null },
        includeUnposted = { value: false }
    ) {
        const _codes = splitCsv(accountCodes).sort();
        const _journalIds = splitCsv(journalIds);
        const _journalTypes = splitCsv(journalTypes);
        const _partnerCategoryNames = splitCsv(partnerCategoryNames);
        const _offset = toNumber(offset, this.locale);
        const _dateRange = parseAccountingDate(dateRange, this.locale);
        const _companyId = companyId?.value ?? null;
        let _includeUnposted = false;
        try {
            _includeUnposted = toBoolean(includeUnposted);
        } catch {
            _includeUnposted = false;
        }
        const value = this.getters.getFerommisFilteredBalance(
            _codes,
            _dateRange,
            _journalIds,
            _journalTypes,
            _partnerCategoryNames,
            _offset,
            _companyId,
            _includeUnposted
        );
        return {
            value,
            format: this.getters.getCompanyCurrencyFormat(_companyId) || "#,##0.00",
        };
    },
});
