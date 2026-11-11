from pydantic import BaseModel, ConfigDict, Field


class Controls(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    max_pages: int = Field(gt=0)
    max_upload_bytes: int = Field(gt=0)
    parser_timeout_seconds: int = Field(gt=0)
    summary_enabled: bool
    summary_input_limit_tokens: int = Field(gt=0)
    summary_max_output_tokens: int = Field(gt=0)
    summary_reasoning_effort: str

    def validate_runtime(self, settings, policy):
        if self.parser_timeout_seconds >= settings.job_timeout_seconds:
            raise ValueError("Parser timeout must be below the worker execution limit.")
        if self.summary_enabled and summary_configuration_error(settings, policy):
            raise ValueError("Repair the environment summary configuration before enabling it.")
        if policy.get("unavailable_code"):
            return
        if self.summary_input_limit_tokens <= policy["token_margin"]:
            raise ValueError("Summary input allowance must exceed the token safety margin.")
        if self.summary_reasoning_effort not in reasoning_options(policy):
            raise ValueError("This reasoning effort is not supported by the configured model.")


class Update(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    revision: int = Field(gt=0)
    values: Controls


def reasoning_options(policy):
    if policy.get("model_id") == "deepseek/deepseek-v4.1-flash-1017":
        return ["none", "low", "high", "max"]
    return ["none", "minimal", "low", "medium", "high", "xhigh", "max"]


def summary_configuration_error(settings, policy):
    if policy.get("unavailable_code"):
        return policy["unavailable_code"]
    if policy["timeout_seconds"] + 30 >= settings.job_timeout_seconds:
        return "SUMMARY_EXECUTION_CONFIG_MISMATCH"
    return None
