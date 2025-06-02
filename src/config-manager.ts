import fs from 'fs/promises';
import path from 'path';
import { existsSync } from 'fs';
import { mkdir } from 'fs/promises';
import os from 'os';
import { VERSION } from './version.js'; // Assuming version.ts is in the same directory
import { CONFIG_FILE } from './config.js'; // Assuming config.ts is in the same directory

export interface ServerConfig {
  blockedCommands?: string[];
  defaultShell?: string;
  allowedDirectories?: string[];
  telemetryEnabled?: boolean;
  fileWriteLineLimit?: number;
  fileReadLineLimit?: number;
  // --- NEW ---
  personasBasePath?: string; // Base path for all persona team folders
  personaActivationMap?: Record<string, { displayName: string; folderName: string }>; // Maps keyphrase to display name and actual folder name under personasBasePath
  // --- END NEW ---
  [key: string]: any;
}

/**
 * Singleton config manager for the server
 */
class ConfigManager {
  private configPath: string;
  private config: ServerConfig = {};
  private initialized = false;

  constructor() {
    this.configPath = CONFIG_FILE;
  }

  /**
   * Initialize configuration - load from disk or create default
   */
  async init() {
    if (this.initialized) return;

    try {
      const configDir = path.dirname(this.configPath);
      if (!existsSync(configDir)) {
        await mkdir(configDir, { recursive: true });
      }

      try {
        await fs.access(this.configPath);
        const configData = await fs.readFile(this.configPath, 'utf8');
        this.config = JSON.parse(configData);
      } catch (error) {
        this.config = this.getDefaultConfig();
        await this.saveConfig();
      }
      this.config['version'] = VERSION; // Ensure version is always current

      // --- NEW: Ensure new config keys have defaults if not present ---
      if (this.config.personasBasePath === undefined) {
        this.config.personasBasePath = this.getDefaultConfig().personasBasePath;
      }
      if (this.config.personaActivationMap === undefined) {
        this.config.personaActivationMap = this.getDefaultConfig().personaActivationMap;
      }
      // --- END NEW ---

      this.initialized = true;
    } catch (error) {
      console.error('Failed to initialize config:', error);
      this.config = this.getDefaultConfig(); // Fallback to default in-memory config
      this.config['version'] = VERSION;
      this.initialized = true; // Mark as initialized even on error to use in-memory defaults
    }
  }

  /**
   * Alias for init() to maintain backward compatibility
   */
  async loadConfig() {
    return this.init();
  }

  /**
   * Create default configuration
   */
  private getDefaultConfig(): ServerConfig {
    return {
      blockedCommands: [
        "mkfs", "format", "mount", "umount", "fdisk", "dd", "parted", "diskpart",
        "sudo", "su", "passwd", "adduser", "useradd", "usermod", "groupadd", "chsh", "visudo",
        "shutdown", "reboot", "halt", "poweroff", "init",
        "iptables", "firewall", "netsh",
        "sfc", "bcdedit", "reg", "net", "sc", "runas", "cipher", "takeown"
      ],
      defaultShell: os.platform() === 'win32' ? 'powershell.exe' : 'bash',
      allowedDirectories: [],
      telemetryEnabled: true,
      fileWriteLineLimit: 50,
      fileReadLineLimit: 1000,
      // --- NEW ---
      personasBasePath: "", // Example: "G:\\My Drive\\__Persona_Architect_System\\3_Generated_Teams"
                            // This will be set by the user via set_config_value
      personaActivationMap: {}, // Example: { "SIU123": { "displayName": "Strategic Intelligence Unit", "folderName": "Strategic Intelligence Unit" } }
                              // This will also be populated by the user
      // --- END NEW ---
      version: VERSION
    };
  }

  /**
   * Save config to disk
   */
  private async saveConfig() {
    try {
      await fs.writeFile(this.configPath, JSON.stringify(this.config, null, 2), 'utf8');
    } catch (error) {
      console.error('Failed to save config:', error);
      // Decide if this should throw or just log. For now, it logs.
      // Depending on robustness requirements, you might want to throw here.
    }
  }

  /**
   * Get the entire config
   */
  async getConfig(): Promise<ServerConfig> {
    if (!this.initialized) { // Ensure config is loaded if accessed before explicit init
        await this.init();
    }
    return { ...this.config };
  }

  /**
   * Get a specific configuration value
   */
  async getValue(key: string): Promise<any> {
    if (!this.initialized) {
        await this.init();
    }
    return this.config[key];
  }

  /**
   * Set a specific configuration value
   */
  async setValue(key: string, value: any): Promise<void> {
    if (!this.initialized) {
        await this.init();
    }

    // Special handling for telemetry opt-out (from original file)
    if (key === 'telemetryEnabled' && value === false) {
      const currentValue = this.config[key];
      if (currentValue !== false) {
        const { capture } = await import('./utils/capture.js'); // Assuming capture.ts is in utils
        await capture('server_telemetry_opt_out', {
          reason: 'user_disabled',
          prev_value: currentValue
        });
      }
    }

    this.config[key] = value;
    await this.saveConfig();
  }

  /**
   * Update multiple configuration values at once
   */
  async updateConfig(updates: Partial<ServerConfig>): Promise<ServerConfig> {
    if (!this.initialized) {
        await this.init();
    }
    this.config = { ...this.config, ...updates };
    await this.saveConfig();
    return { ...this.config };
  }

  /**
   * Reset configuration to defaults
   */
  async resetConfig(): Promise<ServerConfig> {
    this.config = this.getDefaultConfig();
    this.config.version = VERSION; // Ensure version is set on reset
    await this.saveConfig();
    return { ...this.config };
  }
}

export const configManager = new ConfigManager();