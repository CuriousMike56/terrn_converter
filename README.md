Python script to convert legacy Rigs of Rods terrains (0.39 and older) to terrn2 (0.4+) format.

# Features

  - Converts `.terrn` to `.terrn2` format
  - Writes objects, pre-defined vehicles, and road placements to `.tobj` file
  - Converts terrain config `.cfg` to `.otc` format
  - Page file creation, including support for ETTerrain and AlphaSplatTerrain custom terrain materials*
  - Texture processing with GIMP **2.10*** (will not overwrite existing files)
  
[*] Terrains featuring more than six texture layers will not appear correctly in RoR!

[*] GIMP 3 is not currently supported as `gimp-console` infinitely hangs when attempting to process any texture (tested on 3.0.4)

# Usage

`python terrn_converter.py path/to/terrain.terrn`

Optional arguments:

`--filename newname` or `-f newname`

Sets a different file name for the resulting terrn2/tobj/otc files. 

`--displayname "Display Name"` or `-d "Display Name"`

Sets a different name to be shown in the terrain selector.

# Disclaimer

This script was created with the help of GitHub Copilot.
