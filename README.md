# dbus-smartevse - Shows a SmartEVSE EV charger in Venus OS

This driver reads a SmartEVSE over MQTT and shows it as a native EV charger on a Victron GX device.

GitHub repository: `https://github.com/<owner>/<repo>`. The owner of the repository replaces `<owner>/<repo>` in this file with the real GitHub path.

## Index

1. [Disclaimer](#disclaimer)
1. [Purpose](#purpose)
1. [SmartEVSE configuration](#smartevse-configuration)
1. [Configuration](#configuration)
1. [Mode mapping](#mode-mapping)
1. [Install / Update](#install--update)
1. [Uninstall](#uninstall)
1. [Restart](#restart)
1. [Debugging](#debugging)
1. [Compatibility](#compatibility)
1. [Screenshots](#screenshots)


## Disclaimer

The author wrote this driver for personal use. The author is not responsible for any damage that this driver causes.


## Purpose

The driver registers the D-Bus service `com.victronenergy.evcharger.smartevse_<DeviceInstance>`. The default device instance is `43`.

The GX screen and VRM show these values:

- Power in total and per phase
- Current
- Energy of the current charge session
- Charging time
- Status
- Maximum current
- Temperature of the SmartEVSE controller

You can control three things from the GX screen and from VRM:

- The mode (Manual or Auto)
- Start and stop
- The charge current

The driver has two optional feeds. A feed is a stream of values that the driver sends to the SmartEVSE.

- **Battery feed.** The driver sends the power of the home battery to the SmartEVSE. In Solar mode, the SmartEVSE then counts battery charging as surplus for the car. It counts battery discharging against the surplus. The car gets priority over battery charging. The car does not drain the battery. The feed is on by default.
- **Grid feed.** The driver sends the power of the Victron grid meter to the SmartEVSE as its mains meter. The feed is off by default.

The driver never changes the SmartEVSE mode or current without a write by a person. This rule also applies at startup and after a reconnect.


## SmartEVSE configuration

Set up these items in the web interface of the SmartEVSE.

1. **MQTT broker.** Enter the host, the port, the user name, and the password of your MQTT broker. The SmartEVSE connects to one broker only. The driver connects to the same broker. Use the same values in `config.ini`.
1. **Topic prefix.** The default depends on the firmware. Newer firmware uses `SmartEVSE/<serial>`, and older firmware uses `SmartEVSE-<serial>`. Read the prefix on the MQTT page of the SmartEVSE web interface. Use the same prefix in `TopicPrefix` in `config.ini`. The driver takes its `/Serial` value from the part after the last `/`. For a prefix without a `/`, the driver uses the whole prefix.
1. **Mains meter.** The SmartEVSE needs a mains meter for every mode except Normal. Choose the type that fits your setup.
    - If you use the battery feed only, keep your mains meter, for example a HomeWizard P1. The battery feed works with any mains meter type.
    - If you want the grid feed, set the mains meter type to `API`. A SmartEVSE with a HomeWizard P1 ignores the grid feed. A SmartEVSE accepts the grid feed only on a master unit.

The battery feed also works only on a master unit. The SmartEVSE uses it only in Solar mode.


## Configuration

If this is your first install, copy `config.sample.ini` to `config.ini` in the driver folder. Then change the values as you need them. Git ignores `config.ini`, so an update does not overwrite it.

```bash
cp /data/etc/dbus-smartevse/config.sample.ini /data/etc/dbus-smartevse/config.ini
nano /data/etc/dbus-smartevse/config.ini
```

The driver needs `Host` and `TopicPrefix`. All other keys have a default.

### [DEFAULT]

| Key | Meaning | Default |
|---|---|---|
| `DeviceInstance` | Device instance number on D-Bus. | `43` |
| `CustomName` | Name shown on the GX screen and in VRM. | `SmartEVSE` |
| `SignOfLifeLog` | Minutes between sign-of-life log lines. | `10` |
| `NominalVoltage` | Mains voltage in volts. The driver uses it to compute current from power and power from current. | `230` |
| `Position` | Place of the charger in the system. `0` is AC output. `1` is AC input. A wrong value counts the car twice or in the wrong place in the VRM graphs. | `1` |
| `HasEVMeter` | If the SmartEVSE has an EV meter, set `1`. If it has none, set `0`. Without an EV meter, the driver estimates the power and the energy from the allowed current. | `1` |

### [MQTT]

| Key | Meaning | Default |
|---|---|---|
| `Host` | Host name or IP address of the MQTT broker. Required. Example: `192.168.1.10`. | none (required) |
| `Port` | Port of the MQTT broker. | `1883` |
| `Username` | User name of the broker. Leave it empty for none. | empty |
| `Password` | Password of the broker. Leave it empty for none. | empty |
| `TopicPrefix` | Topic prefix of the SmartEVSE. Required. Examples: `SmartEVSE/51446` (newer firmware) and `SmartEVSE-7277` (older firmware). | none (required) |
| `OfflineTimeoutSeconds` | Seconds without MQTT data before the driver shows the charger as offline. The value must be greater than 0. | `60` |

### [BATTERY]

| Key | Meaning | Default |
|---|---|---|
| `Enabled` | Set to `1` to send the battery feed. | `1` |
| `IntervalSeconds` | Seconds between battery updates. The value must be greater than 0. | `10` |

The driver reads `/Dc/Battery/Power` from `com.victronenergy.system`. It sends `round(power / NominalVoltage * 10)` to `<TopicPrefix>/Set/HomeBatteryCurrent`. The unit is deciamps. A positive value means that the battery charges. If the value is missing, the driver stops sending. The SmartEVSE then drops the value after 60 seconds.

### [GRID]

| Key | Meaning | Default |
|---|---|---|
| `Enabled` | Set to `1` to send the grid feed. | `0` |
| `IntervalSeconds` | Seconds between grid updates. The value must be greater than 0. | `2` |

The driver reads the grid power of each phase from `com.victronenergy.system`. It sends the currents of the three phases, the total power, and the import energy to `<TopicPrefix>/Set/MainsMeter`. A positive value means import. If the L1 power is missing, the driver stops sending. If the L2 or the L3 power is missing, the driver sends 0 for that phase. Thus, for a single-phase grid meter, the driver sends 0 for L2 and L3. If the current of one phase is 200 A or more, the driver stops sending. This limit applies to import and to export. When the driver stops sending, the SmartEVSE reports a communication error.


## Mode mapping

The Victron mode `Manual` maps to the SmartEVSE mode `Smart`. The Victron mode `Auto` maps to the SmartEVSE mode `Solar`. The Victron mode `Scheduled` is not supported.

### Mode

| Victron `/Mode` | Command to SmartEVSE | SmartEVSE modes that show as this Victron mode |
|---|---|---|
| 0 Manual | `Smart` | `Smart`, `Normal` |
| 1 Auto | `Solar` | `Solar` |
| 2 Scheduled | Not supported. The driver rejects the write. | None |

If the SmartEVSE is in `Off` or `Pause`, a mode write stores the new mode and sends nothing. The next start sends the stored mode. In all other cases, the driver sends the new mode at once. If the SmartEVSE does not confirm the mode within 10 seconds, the driver logs a warning and shows the mode that the SmartEVSE reports.

The driver stores the last Victron mode in the Venus OS localsettings service. After a restart, it uses the stored mode. Without a stored mode, it uses Auto (Solar). This choice prevents charging from the grid by mistake.

### /StartStop

| Action | Result |
|---|---|
| Write 1 | The driver sends the SmartEVSE mode that matches the current Victron `/Mode` (`Smart` or `Solar`). |
| Write 0 | The driver sends `Pause`. |
| SmartEVSE mode is `Off` or `Pause` | The driver shows 0. `/Mode` keeps its last value. |
| Any other SmartEVSE mode | The driver shows 1. |

### /SetCurrent

| Action | Result |
|---|---|
| Write in amperes | The driver sends `/Set/CurrentOverride` with the value times 10 (deciamps). |
| Write in Auto (Solar) mode | The driver rejects the write. The SmartEVSE ignores overrides in Solar mode. |
| Write below 0 A | The driver rejects the write. |
| Write above the maximum current of the SmartEVSE (`MaxCurrent`) | The driver rejects the write. |
| Write while the charger is offline | The driver rejects the write. |
| Override is not 0 | The driver shows the override in amperes. |
| Override is 0 | The driver shows the current that the SmartEVSE allows now. |

The SmartEVSE accepts an override only in Normal and Smart mode. The value must be between the minimum and the maximum current of the SmartEVSE.


## Install / Update

1. Log in to the GX device with SSH as root. See [Venus OS: Root Access](https://www.victronenergy.com/live/ccgx:root_access#root_access) for details.

2. Download the latest release into `/tmp`. The owner of the repository replaces `<owner>/<repo>` with the real GitHub path first.

    ```bash
    wget -O /tmp/dbus-smartevse.zip https://github.com/<owner>/<repo>/releases/latest/download/dbus-smartevse.zip
    ```

3. Unzip the file into `/data/etc`. The zip has a top folder named `dbus-smartevse`, so the files go to `/data/etc/dbus-smartevse`. The zip has no `config.ini`, so an update keeps yours.

    ```bash
    unzip -o /tmp/dbus-smartevse.zip -d /data/etc
    ```

4. On the first install only, copy `config.sample.ini` to `config.ini`. Then edit `config.ini`. An update keeps your `config.ini`.

    ```bash
    cp /data/etc/dbus-smartevse/config.sample.ini /data/etc/dbus-smartevse/config.ini
    nano /data/etc/dbus-smartevse/config.ini
    ```

5. Run `install.sh`.

    ```bash
    bash /data/etc/dbus-smartevse/install.sh
    ```

    The script sets the file permissions and creates the service link `/service/dbus-smartevse`. It also adds itself to `/data/rc.local`, so the driver survives a firmware update. Daemontools starts the service within seconds.

If you update an existing install, run `bash /data/etc/dbus-smartevse/restart.sh` after step 3.


## Uninstall

Run this command:

```bash
bash /data/etc/dbus-smartevse/uninstall.sh
```

The script removes the line from `/data/rc.local`, stops the service, and removes the service link. Then it asks you a question: delete the driver files and `config.ini`, yes or no? Reboot the device after you uninstall.


## Restart

Run this command:

```bash
bash /data/etc/dbus-smartevse/restart.sh
```

The script kills the Python process. Daemontools then starts it again.


## Debugging

To read the log, run this command:

```bash
tail -n 100 -F /data/log/dbus-smartevse/current | tai64nlocal
```

To see the service status, run this command:

```bash
svstat /service/dbus-smartevse
```

The output looks like `/service/dbus-smartevse: up (pid 5845) 185 seconds`. If the driver cannot start, it logs the cause, waits 60 seconds, and stops. Daemontools then starts it again. If the seconds never go above 60, the driver fails at each start. Read the log to find the cause.

If you see nothing in the log, raise the log level. In `/data/etc/dbus-smartevse/dbus-smartevse.py`, change `level=logging.WARNING` to `level=logging.INFO` or `level=logging.DEBUG`. Then restart the driver.

If the log shows `startup failed` with `NameExistsException`, the service still runs, or another service uses that bus name. Stop the other service or change `DeviceInstance` in `config.ini`.

To make sure that the SmartEVSE sends data, subscribe to its topics on a machine that has the Mosquitto clients:

```bash
mosquitto_sub -h <broker> -t 'SmartEVSE/51446/#' -v
```


## Compatibility

The owner tested the driver on these Venus OS versions:

- Not filled in yet. The owner adds the tested versions here.

The driver needs Python 3.8 or newer. It bundles paho-mqtt 2.1.0 in the `ext` folder. The bundled copy takes priority over any paho-mqtt in Venus OS.


## Versioning

The project uses [semVersie](https://github.com/RonaldPhilipsen/semVersie) to choose a version number for each release. semVersie reads the titles of the merged pull requests. It does not read the code.

Each pull request title must follow the [conventional commits](https://www.conventionalcommits.org/) format:

- `fix: ...` raises the patch number (1.2.3 becomes 1.2.4).
- `feat: ...` raises the minor number (1.2.3 becomes 1.3.0).
- `feat!: ...` marks a breaking change. It raises the major number (1.2.3 becomes 2.0.0).

When a pull request merges into `main`, a GitHub workflow builds `dbus-smartevse.zip` and publishes it as a release. The version shows on the GX device in the `/Mgmt/ProcessVersion` path, together with the Python version. A copy of the code that is not from a release shows `0.0.0-dev`.


## Screenshots

The owner adds screenshots here.
