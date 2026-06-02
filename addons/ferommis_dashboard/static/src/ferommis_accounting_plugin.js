import { EvaluationError } from "@odoo/o-spreadsheet";
import { OdooUIPlugin } from "@spreadsheet/plugins";
import { _t } from "@web/core/l10n/translation";
import { deepCopy } from "@web/core/utils/objects";
import { camelToSnakeObject } from "@spreadsheet/helpers/helpers";
import * as spreadsheet from "@odoo/o-spreadsheet";

const { featurePluginRegistry } = spreadsheet.registries;

export class FerommisAccountingPlugin extends OdooUIPlugin {
    static getters = /** @type {const} */ ([
        "getFerommisFilteredBalance",
        "getFerommisFilteredResidual",
    ]);

    constructor(config) {
        super(config);
        this._serverData = config.custom.odooDataProvider?.serverData;
    }

    get serverData() {
        if (!this._serverData) {
            throw new Error(
                "'serverData' is not defined for FerommisAccountingPlugin."
            );
        }
        return this._serverData;
    }

    /**
     * @param {string[]} codes
     * @param {object} dateRange
     * @param {string[]} journalIds
     * @param {string[]} journalTypes
     * @param {string[]} partnerCategoryNames
     * @param {number} offset
     * @param {number | null} companyId
     * @param {boolean} includeUnposted
     * @returns {number}
     */
    getFerommisFilteredBalance(
        codes,
        dateRange,
        journalIds,
        journalTypes,
        partnerCategoryNames,
        offset,
        companyId,
        includeUnposted
    ) {
        dateRange = deepCopy(dateRange);
        dateRange.year += offset;
        if (dateRange.year < 1900) {
            throw new EvaluationError(_t("%s is not a valid year.", dateRange.year));
        }
        const result = this.serverData.batch.get(
            "account.account",
            "spreadsheet_fetch_balance_ferommis",
            camelToSnakeObject({
                codes,
                dateRange,
                journalIds,
                journalTypes,
                partnerCategoryNames,
                companyId,
                includeUnposted,
            })
        );
        if (result === false) {
            throw new EvaluationError(
                _t("The FEROMMIS-filtered balance could not be computed.")
            );
        }
        return result.balance;
    }

    /**
     * Sum of amount_residual on move lines matching the same filter as
     * getFerommisFilteredBalance. Use this for outstanding receivable /
     * payable amounts where filtering by the invoice journal would otherwise
     * exclude the payments (and overstate the value).
     */
    getFerommisFilteredResidual(
        codes,
        dateRange,
        journalIds,
        journalTypes,
        partnerCategoryNames,
        offset,
        companyId,
        includeUnposted
    ) {
        dateRange = deepCopy(dateRange);
        dateRange.year += offset;
        if (dateRange.year < 1900) {
            throw new EvaluationError(_t("%s is not a valid year.", dateRange.year));
        }
        const result = this.serverData.batch.get(
            "account.account",
            "spreadsheet_fetch_residual_amount",
            camelToSnakeObject({
                codes,
                dateRange,
                journalIds,
                journalTypes,
                partnerCategoryNames,
                companyId,
                includeUnposted,
            })
        );
        if (result === false) {
            throw new EvaluationError(
                _t("The FEROMMIS-filtered residual could not be computed.")
            );
        }
        return result.amount_residual;
    }
}

featurePluginRegistry.add("ferommisAccountingAggregates", FerommisAccountingPlugin);
