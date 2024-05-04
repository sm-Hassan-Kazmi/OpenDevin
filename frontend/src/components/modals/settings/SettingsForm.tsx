import { Input, useDisclosure } from "@nextui-org/react";
import React, { useEffect } from "react";
import { useTranslation } from "react-i18next";
import { FaEye, FaEyeSlash } from "react-icons/fa";
import { useSelector } from "react-redux";
import { AvailableLanguages } from "../../../i18n";
import { I18nKey } from "../../../i18n/declaration";
import { RootState } from "../../../store";
import AgentTaskState from "../../../types/AgentTaskState";
import { AutocompleteCombobox } from "./AutocompleteCombobox";
import { Settings } from "#/services/settings";

interface SettingsFormProps {
  settings: Settings;
  models: string[];
  agents: string[];

  onModelChange: (model: string) => void;
  onAPIKeyChange: (apiKey: string) => void;
  onAgentChange: (agent: string) => void;
  onLanguageChange: (language: string) => void;
}

function SettingsForm({
  settings,
  models,
  agents,
  onModelChange,
  onAPIKeyChange,
  onAgentChange,
  onLanguageChange,
}: SettingsFormProps) {
  const { t } = useTranslation();
  const { curTaskState } = useSelector((state: RootState) => state.agent);
  const [disabled, setDisabled] = React.useState<boolean>(false);
  const { isOpen: isVisible, onOpenChange: onVisibleChange } = useDisclosure();

  useEffect(() => {
    if (
      curTaskState === AgentTaskState.RUNNING ||
      curTaskState === AgentTaskState.PAUSED ||
      curTaskState === AgentTaskState.AWAITING_USER_INPUT
    ) {
      setDisabled(true);
    } else {
      setDisabled(false);
    }
  }, [curTaskState, setDisabled]);

  return (
    <>
      <AutocompleteCombobox
        ariaLabel="model"
        items={models.map((model) => ({ value: model, label: model }))}
        key={settings.LLM_MODEL}
        defaultKey={settings.LLM_MODEL}
        onChange={(e) => {
          onModelChange(e);
        }}
        tooltip={t(I18nKey.SETTINGS$MODEL_TOOLTIP)}
        allowCustomValue // user can type in a custom LLM model that is not in the list
        disabled={disabled}
      />
      <Input
        label="API Key"
        disabled={disabled}
        aria-label="apikey"
        data-testid="apikey"
        placeholder={t(I18nKey.SETTINGS$API_KEY_PLACEHOLDER)}
        type={isVisible ? "text" : "password"}
        value={settings.LLM_API_KEY || ""}
        onChange={(e) => {
          onAPIKeyChange(e.target.value);
        }}
        endContent={
          <button
            className="focus:outline-none"
            type="button"
            onClick={onVisibleChange}
          >
            {isVisible ? (
              <FaEye className="text-2xl text-default-400 pointer-events-none" />
            ) : (
              <FaEyeSlash className="text-2xl text-default-400 pointer-events-none" />
            )}
          </button>
        }
      />
      <AutocompleteCombobox
        ariaLabel="agent"
        key={settings.AGENT}
        items={agents.map((agent) => ({ value: agent, label: agent }))}
        defaultKey={settings.AGENT}
        onChange={onAgentChange}
        tooltip={t(I18nKey.SETTINGS$AGENT_TOOLTIP)}
        disabled={disabled}
      />
      <AutocompleteCombobox
        ariaLabel="language"
        key={settings.LANGUAGE}
        items={AvailableLanguages}
        defaultKey={settings.LANGUAGE}
        onChange={onLanguageChange}
        tooltip={t(I18nKey.SETTINGS$LANGUAGE_TOOLTIP)}
        disabled={disabled}
      />
    </>
  );
}

export default SettingsForm;
