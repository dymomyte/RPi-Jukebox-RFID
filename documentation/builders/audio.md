# Audio

## Configuration

The Jukebox supports 2 audio outputs, primary and secondary. The **primary output** is the default output and must
be available after system boot. This will typically be your sound card or the Pi's built-in headphone output.

The **secondary output** is an optional alternative output where the audio stream can be routed to.
Stream transfer happens on user input or automatically on the connection of an audio device.
This is mainly targeted at Bluetooth Headsets/Speakers.

Audio outputs run via PipeWire (with `wireplumber` as the session manager) and the basic configuration should be
easy. There is a [configuration tool](../developers/coreapps.md#Audio), to setup the configuration for the Jukebox
Core App.

### To set up the audio

1. Follow the setup steps according to your sound card
2. Check that the sound output works [as described below](audio.md#checking-system-sound-output)
3. Run the [audio configuration tool](../developers/coreapps.md#Audio)

#### Checking system sound output

Run the following steps in a console:

<!-- markdownlint-disable MD010 -->
```bash
# Check available audio sinks
$ wpctl status

# Set the default sink (id from `wpctl status`)
$ wpctl set-default <id>

# Check volume level (exit with ESC)
$ alsamixer

# Play a sound
$ pw-play /usr/share/sounds/alsa/Front_Center.wav

# This must also work when using an ALSA device
$ aplay /usr/share/sounds/alsa/Front_Center.wav
```
<!-- markdownlint-restore -->

You can also play a sound to a specific sink without changing the default. Use
the sink ID shown by `wpctl status`:

```bash
$ pw-play --target=<id> /usr/share/sounds/alsa/Front_Center.wav
```

## Bluetooth

Bluetooth setup consists of three steps

1. Pair and connect your Bluetooth device
2. Check the output works
3. Re-run the config tool

To pair and connect, follow these steps. This will be a one-time setup.

```bash
$ bluetoothctl
Agent registered
[CHG] Controller B8:27:EB:44:C4:33 Pairable: yes
#### Put your headset into pairing mode
[bluetooth]# scan on
Discovery started
#### Wait a few seconds for your device to appear
....
[NEW] Device C4:FB:20:63:CO:FE PowerLocus Buddy
....
[bluetooth]# scan off
....
[bluetooth]# pair C4:FB:20:63:CO:FE
....
Pairing successful
....
[bluetooth]# trust C4:FB:20:63:CO:FE
....
[bluetooth]# connect C4:FB:20:63:CO:FE
....
[PowerLocus Buddy]# exit
```

If `bluetoothctl` has trouble to execute due to permission issue, try `sudo bluetoothctl`.

Wait for a few seconds and then with `$ wpctl status`, check whether the Bluetooth device shows up as an output.
The sink name usually looks like this: `bluez_output.C4_FB_20_63_CO_FE.1`.

Run through the steps above to check whether the output is working or not.
If it does not work immediately, turn your headset off and on to force a reconnect.

Rerun the config tool to register the Bluetooth device with the Jukebox core app as its secondary audio output.

## Sound card silent at low volume

Some (mostly USB) sound cards output nothing at the bottom of their volume range. The volume slider then has
to pass a certain value before you hear anything, e.g. 19 out of 100. The card reports volume steps that it
actually plays as silence, and the audio server uses them.

### Find the cut-off

Look up the card's playback volume control, its range of steps and its decibel range:

```bash
$ amixer -c <card> contents
...
numid=6,iface=MIXER,name='Speaker Playback Volume'
  ; type=INTEGER,access=rw---R--,values=2,min=0,max=1008,step=0
  : values=27,27
  | dBminmax-min=-63.00dB,max=0.00dB
```

While music plays, set the control to different steps, starting at the bottom, and listen. Note the lowest step
that makes a sound, and the decibel value `amixer` reports for it:

```bash
$ amixer -c <card> sset Speaker 17
$ amixer -c <card> sget Speaker
  Front Left: Playback 17 [2%] [-61.94dB] [on]
```

There are two ways to deal with the silent steps. Both are configured per output.

### Option 1: Volume floor

Set `volume_floor` for the output in `jukebox.yaml` (see [Best practice procedure](configuration.md#best-practice-procedure)).
It is the system volume (in percent) that stands for 0 %; the volume range 1...100 % is scaled into
`volume_floor...volume_limit`. Choose it so that volume 1 lands on the lowest audible step. This needs no system
changes, but the quietest volume is only as quiet as that step.

```yaml
pulse:
  outputs:
    primary:
      volume_limit: 100
      volume_floor: 8.87
```

### Option 2: Software volume below the cut-off

The audio server uses the card's hardware volume as far down as the card claims to go, and software volume below
that. A *decibel fix* tells it where the card's usable range really starts, so the hardware still does all audible
volume levels and software volume fades smoothly to silence below them. Leave `volume_floor` at 0 for this option.

1. Find the card's USB vendor and product ID with `lsusb` (e.g. `ID 0c76:1203`).
2. Copy the default profile set under a new name and add a decibel fix for the volume control. List the lowest
   audible step with its decibel value, and the highest step with its decibel value:

    ```bash
    $ sudo mkdir -p /etc/alsa-card-profile/mixer/profile-sets
    $ sudo cp /usr/share/alsa-card-profile/mixer/profile-sets/default.conf \
        /etc/alsa-card-profile/mixer/profile-sets/usb-sound-card-dbfix.conf
    $ sudo tee -a /etc/alsa-card-profile/mixer/profile-sets/usb-sound-card-dbfix.conf <<EOF

    [DecibelFix Speaker]
    db-values = 17:-61.94 1008:0.00
    EOF
    ```

3. Assign the profile set to the card with a udev rule, using its IDs:

    ```bash
    $ echo 'SUBSYSTEM=="sound", ACTION=="change", KERNEL=="card*", ATTRS{idVendor}=="0c76", ATTRS{idProduct}=="1203", ENV{ACP_PROFILE_SET}="usb-sound-card-dbfix.conf"' \
        | sudo tee /etc/udev/rules.d/91-usb-sound-card-dbfix.rules
    $ sudo udevadm control --reload
    $ sudo udevadm trigger --action=change --subsystem-match=sound
    ```

4. Restart the audio server and the Jukebox:

    ```bash
    $ systemctl --user restart wireplumber pipewire pipewire-pulse
    $ systemctl --user restart jukebox-daemon
    ```

5. Check: with the volume set very low, `amixer -c <card> sget Speaker` must stay at the step from the decibel fix.

> [!NOTE]
> On systems running PulseAudio instead of PipeWire, put the profile set into
> `/usr/share/pulseaudio/alsa-mixer/profile-sets/`, set `ENV{PULSE_PROFILE_SET}` in the udev rule
> and restart `pulseaudio` instead.

## Additional options

For other audio configuration options, please look at the `jukebox.yaml` for now.

Directly edit `jukebox.yaml` following the steps: [Best practice procedure](configuration.md#best-practice-procedure).
