import { AvailableLanguages } from "#/i18n";
import { I18nKey } from "#/i18n/declaration";
import { initializeAgent } from "#/services/agent";
import { getSettings, getSettingsDifference } from "#/services/settings";
import {
  Settings,
  fetchAgents,
  fetchModels,
  saveSettings,
} from "#/services/settingsService";
import toast from "#/utils/toast";
import { Spinner } from "@nextui-org/react";
import i18next from "i18next";
import React from "react";
import { useTranslation } from "react-i18next";
import BaseModal from "../base-modal/BaseModal";
import SettingsForm from "./SettingsForm";

interface SettingsProps {
  isOpen: boolean;
  onOpenChange: (isOpen: boolean) => void;
}

function SettingsModal({ isOpen, onOpenChange }: SettingsProps) {
  const { t } = useTranslation();
  const currentSettings = getSettings();

  const [models, setModels] = React.useState<string[]>([]);
  const [agents, setAgents] = React.useState<string[]>([]);
  const [settings, setSettings] = React.useState<Settings>(currentSettings);

  const [loading, setLoading] = React.useState(true);

  React.useEffect(() => {
    (async () => {
      try {
        setModels(await fetchModels());
        setAgents(await fetchAgents());
      } catch (error) {
        console.error(error);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const handleModelChange = (model: string) => {
    setSettings((prev) => ({ ...prev, LLM_MODEL: model }));
    // Needs to also reset the API key.
    const key = localStorage.getItem(
      `API_KEY_${settings.LLM_MODEL || models[0]}`,
    );
    setSettings((prev) => ({ ...prev, LLM_API_KEY: key || "" }));
  };

  const handleAgentChange = (agent: string) => {
    setSettings((prev) => ({ ...prev, AGENT: agent }));
  };

  const handleLanguageChange = (language: string) => {
    const key = AvailableLanguages.find(
      (lang) => lang.label === language,
    )?.value;

    if (key) setSettings((prev) => ({ ...prev, LANGUAGE: key }));
  };

  const handleAPIKeyChange = (key: string) => {
    localStorage.setItem(`API_KEY_${settings.LLM_MODEL || models[0]}`, key);
    setSettings((prev) => ({ ...prev, LLM_API_KEY: key || "" }));
  };

  const handleSaveSettings = () => {
    const updatedSettings = getSettingsDifference(settings);
    saveSettings(settings);
    i18next.changeLanguage(settings.LANGUAGE);
    initializeAgent(settings); // reinitialize the agent with the new settings

    Object.entries(updatedSettings).forEach(([key, value]) => {
      toast.settingsChanged(`${key} set to "${value}"`);
    });
  };

  return (
    <BaseModal
      isOpen={isOpen}
      onOpenChange={onOpenChange}
      title={t(I18nKey.CONFIGURATION$MODAL_TITLE)}
      subtitle={t(I18nKey.CONFIGURATION$MODAL_SUB_TITLE)}
      actions={[
        {
          label: t(I18nKey.CONFIGURATION$MODAL_SAVE_BUTTON_LABEL),
          action: handleSaveSettings,
          isDisabled:
            Object.values(settings).some((value) => !value) ||
            JSON.stringify(settings) === JSON.stringify(currentSettings),
          closeAfterAction: true,
          className: "bg-primary rounded-lg",
        },
        {
          label: t(I18nKey.CONFIGURATION$MODAL_CLOSE_BUTTON_LABEL),
          action: () => {
            setSettings(currentSettings); // reset settings from any changes
          },
          closeAfterAction: true,
          className: "bg-neutral-500 rounded-lg",
        },
      ]}
    >
      {loading && <Spinner />}
      {!loading && (
        <SettingsForm
          settings={settings}
          models={models}
          agents={agents}
          onModelChange={handleModelChange}
          onAgentChange={handleAgentChange}
          onLanguageChange={handleLanguageChange}
          onAPIKeyChange={handleAPIKeyChange}
        />
      )}
    </BaseModal>
  );
}

export default SettingsModal;
