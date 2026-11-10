import pytest

from fraudinv.contract import FeatureContract, ForbiddenFeatureError

BALANCES = ["oldbalanceOrg", "newbalanceOrig", "oldbalanceDest", "newbalanceDest"]


@pytest.fixture(scope="module")
def contract():
    return FeatureContract.load()


def test_primary_and_candidate_features_validate(contract):
    names = ["type_onehot", "log1p_amount", "dest_has_prior", "dest_prior_count",
             "dest_prior_amount_sum", "dest_prior_count_24h", "dest_steps_since_last"]
    assert contract.validate_feature_set(names) == names


@pytest.mark.parametrize("field", BALANCES + ["isFraud", "isFlaggedFraud", "nameOrig",
                                              "nameDest", "source_row", "event_id"])
def test_raw_forbidden_fields_rejected(contract, field):
    with pytest.raises(ForbiddenFeatureError):
        contract.validate_feature_set(["log1p_amount", field])


@pytest.mark.parametrize("name", ["balance_delta_orig", "OLDBALANCEORG_log", "dest_balance_ratio",
                                  "isFraud_rolling", "label_rate_24h", "nameDest_target_mean"])
def test_derived_names_rejected(contract, name):
    with pytest.raises(ForbiddenFeatureError):
        contract.validate_feature_set([name])


def test_neutrally_named_balance_derivative_rejected_by_lineage(contract):
    # A name that dodges every pattern is still rejected via its declared inputs.
    spec = {"orig_drain": {"inputs": ["oldbalanceOrg", "amount"]}}
    with pytest.raises(ForbiddenFeatureError, match="forbidden inputs"):
        contract.validate_feature_set(["orig_drain"], extra_specs=spec)


def test_undeclared_feature_rejected(contract):
    with pytest.raises(ForbiddenFeatureError, match="not declared"):
        contract.validate_feature_set(["amount_zscore_fullfile"])


def test_ablation_feature_needs_explicit_flag(contract):
    with pytest.raises(ForbiddenFeatureError, match="ablation-only"):
        contract.validate_feature_set(["log1p_amount", "hour_of_day"])
    assert contract.validate_feature_set(["hour_of_day"], allow_ablation=True) == ["hour_of_day"]


def test_model_matrix_columns_checked(contract):
    contract.check_frame_columns(["type_onehot=TRANSFER", "type_onehot=CASH_OUT", "log1p_amount"])
    with pytest.raises(ForbiddenFeatureError):
        contract.check_frame_columns(["log1p_amount", "newbalanceDest"])
    with pytest.raises(ForbiddenFeatureError):
        contract.check_frame_columns(["log1p_amount", "isFlaggedFraud"])


def test_contract_declares_every_feature_input_safely(contract):
    # The frozen file itself must not declare a feature fed by a forbidden field.
    for name, spec in contract.features.items():
        contract.check_inputs(name, spec.get("inputs", []))
        contract.check_name(name)
