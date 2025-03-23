import os
import sys
import uuid
import subprocess  # For calling GIMP in batch mode

def extract_texture_name(texture_line):
    """Extract texture filename from a texture_unit line"""
    # Skip comment lines
    if texture_line.strip().startswith('//'):
        return None
    # Find texture keyword and extract name
    if 'texture' in texture_line:
        tex = texture_line.split('texture')[1].strip()
        # Remove any trailing comments
        tex = tex.split('//')[0].strip()
        # Clean up any remaining braces and whitespace
        return tex.replace('}', '').replace('{', '').strip()
    return None

def parse_etterrain_material(material_file, material_name):
    """Parse an ETTerrain material definition and return texture info"""
    try:
        print(f"\nSearching for material '{material_name}' in {os.path.basename(material_file)}")
        with open(material_file, 'r') as f:
            content = f.read()
            
        # Find the material section with case-insensitive search
        content_lower = content.lower()
        search_pattern = f"material {material_name}".lower()
        material_start = content_lower.find(search_pattern)
        if material_start == -1:
            print("Material not found in file")
            return None
            
        print("Found material, checking type...")
            
        # Get the actual material section using the found position
        material_section = content[material_start:]
        material_end = material_section.find("\nmaterial ")
        if material_end != -1:
            material_section = material_section[:material_end]

        # Check for material inheritance
        if ": AlphaSplatTerrain" in material_section:
            print("Found AlphaSplatTerrain material, extracting textures...")
            return parse_alphasplat_material(material_section)
            
        # Check for ETTerrain identifiers
        et_identifiers = [
            "et/program",
            "etterrain",
            "etambient"
        ]
        
        material_text = f"{material_name} {material_section}".lower()
        is_et_material = any(id in material_text for id in et_identifiers)
                
        if not is_et_material:
            print("Not a supported terrain material type")
            return None

        print("Found ETTerrain material, extracting textures...")
        textures = {
            'blendmaps': [],
            'layers': []
        }
        
        # Find Lighting and Splatting passes
        print("\nExtracting texture information:")
        lighting_pass = material_section[material_section.find("pass Lighting"):material_section.find("pass Splatting")]
        splatting_pass = material_section[material_section.find("pass Splatting"):material_section.find("pass", material_section.find("pass Splatting") + 1)]
        
        # Extract RGB blendmaps
        print("\nProcessing blendmaps:")
        texture_units = lighting_pass.split('texture_unit')
        for unit in texture_units[1:4]:
            if '_RGB' in unit:
                tex = extract_texture_name(unit)
                print(f"  Found blendmap: {tex}")
                textures['blendmaps'].append(tex)
                
        # Get normal maps
        print("\nProcessing normal maps:")
        normal_maps = []
        for unit in texture_units[4:]:
            if '_NRM' in unit:
                tex = extract_texture_name(unit)
                if tex:
                    print(f"  Found normal map: {tex}")
                    normal_maps.append(tex)
                    
        # Get diffuse textures
        print("\nProcessing diffuse textures:")
        diffuse_maps = []
        splatting_units = splatting_pass.split('texture_unit')
        for unit in splatting_units[4:]:
            if 'texture' in unit and not '_RGB' in unit:
                tex = extract_texture_name(unit)
                if tex and not tex.endswith(('_NRM.dds', '_lightmap.dds')):
                    print(f"  Found diffuse texture: {tex}")
                    diffuse_maps.append(tex)
        
        # Create texture layers
        print("\nPairing textures:")
        for i in range(len(normal_maps)):
            if i < len(diffuse_maps):
                print(f"  Layer {i+1}: {diffuse_maps[i]} + {normal_maps[i]}")
                textures['layers'].append((diffuse_maps[i], normal_maps[i]))
                
        print(f"\nFound {len(textures['layers'])} texture layers total")
        return textures
        
    except Exception as e:
        print(f"Error parsing material file: {e}")
        return None

def parse_alphasplat_material(material_section):
    """Parse an AlphaSplatTerrain material definition"""
    textures = {
        'blendmaps': [],
        'layers': []
    }
    
    # Extract alpha masks
    fp_section = material_section[material_section.find("fragment_program_ref AlphaSplatTerrain/FP"):] 
    fp_end = fp_section.find("}")
    fp_section = fp_section[:fp_end]
    
    alpha0_mask = [1,1,1,0]  # Default mask
    alpha1_mask = [1,1,1,0]
    
    if "alpha0Mask" in fp_section:
        alpha0_line = fp_section[fp_section.find("alpha0Mask"):].split('\n')[0]
        alpha0_mask = [float(x) for x in alpha0_line.split("float4")[1].strip().split()]
    if "alpha1Mask" in fp_section:
        alpha1_line = fp_section[fp_section.find("alpha1Mask"):].split('\n')[0]
        alpha1_mask = [float(x) for x in alpha1_line.split("float4")[1].strip().split()]

    # Get blend maps
    for i, line in enumerate(material_section.split('\n')):
        if 'set_texture_alias AlphaMap' in line:
            tex = line.split()[2].strip()
            textures['blendmaps'].append(tex)

    # Get splat textures and pair with blank normal maps
    splat_count = 8
    splats = []
    for i in range(1, splat_count + 1):
        for line in material_section.split('\n'):
            if f'set_texture_alias Splat{i}' in line:
                tex = line.split()[2].strip()
                splats.append(tex)
                break

    # Create texture layers based on enabled alpha channels
    for i, (splat, enabled) in enumerate(zip(splats[:4], alpha0_mask)):
        if enabled == 1:
            blend_map = textures['blendmaps'][0]
            rgb_channel = ['R', 'G', 'B', 'A'][i]
            textures['layers'].append((splat, 'blank_NRM.dds'))
            
    for i, (splat, enabled) in enumerate(zip(splats[4:], alpha1_mask)):
        if enabled == 1:
            blend_map = textures['blendmaps'][1]
            rgb_channel = ['R', 'G', 'B', 'A'][i]
            textures['layers'].append((splat, 'blank_NRM.dds'))

    return textures

def get_gimp_path():
    """Find GIMP console executable in common installation locations."""
    appdata_local = os.getenv('LOCALAPPDATA', '')
    
    possible_paths = [
        r"C:\Program Files\GIMP 2\bin\gimp-console-2.10.exe",
        os.path.join(appdata_local, r"Programs\GIMP 2\bin\gimp-console-2.10.exe")
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return path
            
    raise FileNotFoundError("Could not find GIMP console executable")

def process_texture_with_gimp(input_texture, output_texture):
    """Process a texture using GIMP to add a black alpha mask and save as DDS with DXT5 compression."""
    # Check if output texture already exists
    if os.path.exists(output_texture):
        print(f"Using existing processed texture: {output_texture}")
        return True
        
    try:
        # Escape file paths for GIMP
        input_texture = input_texture.replace("\\", "/")
        output_texture = output_texture.replace("\\", "/")
        
        # Get GIMP console path
        gimp_console_path = get_gimp_path()
        
        # GIMP batch script with correct argument types
        gimp_script = f"""
        (let* ((image (car (gimp-file-load RUN-NONINTERACTIVE "{input_texture}" "{input_texture}")))
               (drawable (car (gimp-image-get-active-layer image))))
          (gimp-layer-add-alpha drawable)
          (gimp-edit-fill drawable TRANSPARENT-FILL)
          (file-dds-save 
            RUN-NONINTERACTIVE  ; [1] run-mode
            image              ; [2] image
            drawable           ; [3] drawable
            "{output_texture}" ; [4] filename
            "{output_texture}" ; [5] raw-filename
            0                  ; [6] format (auto)
            1                  ; [7] mipmaps
            0                  ; [8] save-type
            0                  ; [9] compression
            5                  ; [10] format-version (5 = DXT5)
            0                  ; [11] transparent-index
            0                  ; [12] coverage
            0                  ; [13] use-perceptual-metric
            0                  ; [14] alpha-test-threshold
            0                  ; [15] color-metric-given
            0                  ; [16] color-metric
            0                  ; [17] alpha-dither
            0)                ; [18] dither
          (gimp-image-delete image))
        """
        
        # Run GIMP in console mode
        result = subprocess.run(
            [gimp_console_path, "-i", "-b", gimp_script, "-b", "(gimp-quit 0)"],
            capture_output=True,
            text=True,
            check=True
        )
       # print(f"GIMP stderr: {result.stderr}")
       # print(f"GIMP output: {result.stdout}")
        print(f"Processed texture: {output_texture}")
    except subprocess.CalledProcessError as e:
        print(f"Error processing texture with GIMP: {e}")
        print(f"GIMP stderr: {e.stderr}")

def convert_dds_to_png(input_texture, output_texture):
    """Convert DDS texture to PNG using GIMP"""
    if os.path.exists(output_texture):
        print(f"Using existing converted texture: {output_texture}")
        return True
        
    try:
        input_texture = input_texture.replace("\\", "/")
        output_texture = output_texture.replace("\\", "/")
        gimp_console_path = get_gimp_path()
        
        gimp_script = f"""
        (let* ((image (car (gimp-file-load RUN-NONINTERACTIVE "{input_texture}" "{input_texture}")))
               (drawable (car (gimp-image-get-active-layer image))))
          (file-png-save-defaults RUN-NONINTERACTIVE image drawable "{output_texture}" "{output_texture}")
          (gimp-image-delete image))
        """
        
        result = subprocess.run(
            [gimp_console_path, "-i", "-b", gimp_script, "-b", "(gimp-quit 0)"],
            capture_output=True,
            text=True,
            check=True
        )
        print(f"Converted texture to PNG: {output_texture}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error converting texture to PNG: {e}")
        print(f"GIMP stderr: {e.stderr}")
        return False

def copy_default_textures(output_dir):
    """Copy default terrain textures from textures folder to output directory"""
    default_tex_dir = os.path.join(os.path.dirname(__file__), "textures")
    default_textures = [
        "blank_NRM.dds",
        "terrain_detail_ds.dds",
        "terrain_detail_dark_ds.dds",
        "terrain_detail_nrm.dds"
    ]
    
    for texture in default_textures:
        src = os.path.join(default_tex_dir, texture)
        dst = os.path.join(output_dir, texture)
        if os.path.exists(src) and not os.path.exists(dst):
            import shutil
            shutil.copy2(src, dst)
            print(f"Copied default texture: {texture}")

def convert_cfg_to_otc(cfg_file):
    try:
        print(f"Converting {cfg_file} to otc format...")
        
        # Read values from .cfg
        heightmap_size = None
        heightmap_bpp = None
        heightmap_flip = False
        world_size_x = None
        world_size_z = None
        max_height = None
        max_pixel_error = "0"
        heightmap_image = None
        world_texture = None
        terrain_name = os.path.splitext(os.path.basename(cfg_file))[0]
        custom_material = None
        
        with open(cfg_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line.startswith('#') or not line:
                    continue
                    
                if 'Heightmap.image=' in line:
                    heightmap_image = line.split('=')[1]
                elif 'WorldTexture=' in line:
                    world_texture = line.split('=')[1]
                elif 'Heightmap.raw.size=' in line:
                    heightmap_size = line.split('=')[1]
                elif 'Heightmap.raw.bpp=' in line:
                    heightmap_bpp = line.split('=')[1]
                elif 'Heightmap.flip=' in line and line.split('=')[1].lower() == 'true':
                    heightmap_flip = True
                elif 'PageWorldX=' in line:
                    world_size_x = line.split('=')[1]
                elif 'PageWorldZ=' in line:
                    world_size_z = line.split('=')[1]
                elif 'MaxHeight=' in line:
                    max_height = line.split('=')[1]
                elif 'MaxPixelError=' in line:
                    max_pixel_error = line.split('=')[1]
                elif 'CustomMaterialName=' in line:
                    custom_material = line.split('=')[1].strip()
        
        if not all([heightmap_size, heightmap_bpp, world_size_x, world_size_z, max_height]):
            print("Error: Missing required values in cfg file")
            return False
            
        # Create main .otc file
        otc_path = os.path.splitext(cfg_file)[0] + '.otc'
        with open(otc_path, 'w') as f:
            f.write(f'Heightmap.0.0.raw.size={heightmap_size}\n')
            f.write(f'Heightmap.0.0.raw.bpp={heightmap_bpp}\n')
            f.write(f'Heightmap.0.0.flipX={1 if heightmap_flip else 0}\n')
            f.write('\n')
            f.write(f'WorldSizeX={world_size_x}\n')
            f.write(f'WorldSizeZ={world_size_z}\n')
            f.write(f'WorldSizeY={max_height}\n')
            f.write('\n')
            f.write('disableCaching=1\n')
            f.write('\n')
            f.write(f'PageFileFormat={terrain_name}-page-0-0.otc\n')
            f.write('\n')
            f.write(f'MaxPixelError={max_pixel_error}\n')
            f.write('LightmapEnabled=0\n')
            f.write('SpecularMappingEnabled=1\n')
            f.write('NormalMappingEnabled=1\n')
        print(f"Created {otc_path}")
            
        # Create page files
        if custom_material:
            print(f"\nFound custom material name: {custom_material}")
            material_dir = os.path.dirname(cfg_file)
            material_files = [f for f in os.listdir(material_dir) if f.endswith('.material')]
            
            material_textures = None
            for mat_file in material_files:
                material_textures = parse_etterrain_material(os.path.join(material_dir, mat_file), custom_material)
                if material_textures:
                    break
                    
            if material_textures:
                # Process diffuse textures through GIMP
                processed_diffuse_textures = []
                for diffuse, _ in material_textures['layers']:
                    input_texture = os.path.join(os.path.dirname(cfg_file), diffuse)
                    output_texture = os.path.splitext(input_texture)[0] + "_diffusespecular.dds"
                    process_texture_with_gimp(input_texture, output_texture)
                    # Store only the filename, not the full path
                    processed_diffuse_textures.append(os.path.basename(output_texture))

                # Ensure blank_NRM.dds is available
                copy_default_textures(os.path.dirname(cfg_file))

                # Create page file with processed textures
                page_path = os.path.join(os.path.dirname(cfg_file), f'{terrain_name}-page-0-0.otc')
                with open(page_path, 'w') as f:
                    f.write(f'{heightmap_image}\n')
                    f.write(f'{len(material_textures["layers"])}\n')
                    f.write('; worldSize, diffusespecular, normalheight, blendmap, blendmapmode, alpha\n')
                    
                    for i, (diffuse, normal) in enumerate(material_textures['layers']):
                        blend_idx = i // 3
                        rgb_channel = ['R', 'G', 'B'][i % 3]
                        if blend_idx < len(material_textures['blendmaps']):
                            blendmap = material_textures['blendmaps'][blend_idx]
                            f.write(f'6, {processed_diffuse_textures[i]}, {normal}, {blendmap}, {rgb_channel}, 0.99\n')
                
                print(f"Created {page_path}")
                return True
        else:
            # Process the base diffuse texture for simple terrain
            if world_texture:
                base_name, ext = os.path.splitext(world_texture)
                input_texture = os.path.join(os.path.dirname(cfg_file), world_texture)
                base_texture = f"{base_name}_diffusespecular.dds"  # Just the filename
                base_texture_path = os.path.join(os.path.dirname(cfg_file), base_texture)
                process_texture_with_gimp(input_texture, base_texture_path)
                
                # Convert base texture to PNG for detail layer
                detail_texture = f"{base_name}.png"
                detail_texture_path = os.path.join(os.path.dirname(cfg_file), detail_texture)
                convert_dds_to_png(input_texture, detail_texture_path)
            else:
                base_texture = f'{terrain_name}_DS.dds'
                detail_texture = f'{terrain_name}.png'

            # Copy default textures before creating the page file
            copy_default_textures(os.path.dirname(cfg_file))

            # Create page-0-0.otc file for simple terrain
            page_path = os.path.join(os.path.dirname(cfg_file), f'{terrain_name}-page-0-0.otc')
            with open(page_path, 'w') as f:
                f.write(f'{heightmap_image}\n')
                
                # Write number of texture layers
                f.write('2\n')
                
                # Write base layer
                f.write(f'; worldSize, diffusespecular, normalheight, blendmap, blendmapmode, alpha\n')
                f.write(f'{world_size_x}, {base_texture}, blank_NRM.dds\n')
                
                # Write detail layer with converted texture
                f.write('10, terrain_detail_dark_ds.dds, terrain_detail_nrm.dds, ' + detail_texture + ', R, 0.8\n')

            print(f"Created {page_path}")
            return True
        
    except Exception as e:
        print(f"Error converting cfg file: {e}")
        return False

def convert_terrn_to_terrn2(input_file):
    try:
        print(f"Converting {input_file} to terrn2 format...")
        output_name = os.path.splitext(input_file)[0] + '.terrn2'
        
        terrain_name = ""
        ogre_cfg = ""
        water_height = None
        water_color = ""
        start_position = ""
        objects = []
        authors = {}
        gravity = "-9.81"
        landuse_cfg = None
        has_caelum = False
        
        with open(input_file, 'r') as f:
            lines = f.readlines()
            
            for line in lines:
                line = line.strip()
                if not line or line.startswith("//end"):
                    continue
                    
                # Extract authors from comments
                if (line.lower().startswith("//author") or 
                    line.lower().startswith(";author")):
                    parts = line[2:] if line.startswith("//") else line[1:]
                    parts = parts.split(" ")
                    if len(parts) >= 3:
                        # Combine "author" and type (e.g., "author terrain" -> "terrain")
                        author_type = parts[1]  # get terrain, texture, etc.
                        author_name = " ".join(parts[3:])  # Skip "author", type, and ID to get name
                        
                        # Remove email if present
                        if '@' in author_name:
                            author_name = author_name.split()[0]
                            
                        authors[author_type] = author_name
                    continue
                    
                # Extract gravity value
                if line.startswith("gravity "):
                    gravity = line.split(" ")[1]
                    continue
                    
                # Extract landuse config
                if line.startswith("landuse-config "):
                    landuse_cfg = line.split(" ")[1]
                    continue
                    
                # Check for caelum config
                if line.startswith("caelumconfig"):
                    has_caelum = True
                    continue
                    
                # First 5 lines are header info
                if not terrain_name:
                    terrain_name = line
                elif not ogre_cfg:
                    ogre_cfg = line
                elif line == "caelum":  # Skip the caelum keyword if it's the third line
                    continue
                elif line.startswith("w "):
                    water_height = line.split(" ")[1]
                elif not water_color:
                    water_color = line
                elif not start_position:
                    start_position = line.split(",")[0:3]  # Only take first 3 coordinates
                # Rest are objects
                elif not line.startswith("//"):
                    objects.append(line)

        tobj_name = os.path.splitext(ogre_cfg)[0] + ".tobj"
        output_dir = os.path.dirname(input_file)
        tobj_path = os.path.join(output_dir, tobj_name)

        try:
            # Create terrn2 file first
            with open(output_name, 'w') as f:
                f.write('[General]\n')
                f.write(f'Name = {terrain_name}\n')
                f.write(f'GeometryConfig = {os.path.splitext(ogre_cfg)[0]}.otc\n')
                if water_height:
                    f.write('Water=1\n')
                    f.write(f'WaterLine = {water_height}\n')
                else:
                    f.write('Water=0\n')
                f.write(f'AmbientColor = {water_color}\n')
                f.write(f'StartPosition = {", ".join(start_position)}\n')
                if has_caelum:
                    f.write(f'CaelumConfigFile = {os.path.basename(input_file)}.os\n')
                else:
                    f.write('#CaelumConfigFile =\n')
                f.write('SandStormCubeMap = tracks/skyboxcol\n')
                f.write(f'Gravity = {gravity}\n')
                f.write('CategoryID = 129\n')
                f.write('Version = 1\n')
                f.write(f'GUID = {str(uuid.uuid4())}\n')
                if landuse_cfg:
                    f.write(f'TractionMap = {landuse_cfg}\n')
                f.write('\n\n')
                
                f.write('[Authors]\n')
                for author_type, author_name in authors.items():
                    f.write(f'{author_type} = {author_name}\n')
                if not authors:
                    f.write('terrain = unknown\n')
                f.write(f'terrn2 = cm_terrn_converter\n\n')
                
                f.write(' \n[Objects]\n')
                f.write(f'{tobj_name}=\n\n')
                
                f.write('[Scripts]\n')
            print(f"Created {output_name}")

            # Create .tobj file second
            with open(tobj_path, 'w') as f:
                header_count = 0
                found_first_object = False
                
                for obj in lines:
                    # Skip the first 5 header lines
                    if header_count < 5:
                        header_count += 1
                        continue
                        
                    # Skip empty lines, metadata comments and author comments
                    if (not obj.strip() or 
                        '//fileinfo' in obj or ';fileinfo' in obj or 
                        '//author' in obj.lower() or ';author' in obj.lower() or
                        ((obj.strip().startswith('//') or obj.strip().startswith(';')) and 
                         any(c.isdigit() for c in obj.split('=')[0]) and 
                         '=' in obj)):
                        continue
                        
                    # Skip the start position coordinates 
                    if not found_first_object and ',' in obj:
                        coords = obj.split(',')
                        if len(coords) == 9:  # Start position has 9 coordinates
                            continue
                        found_first_object = True
                    
                    # Skip caelumconfig and landuse-config lines
                    line = obj.strip()
                    if (line.startswith('caelumconfig') or
                        line.startswith('landuse-config')):
                        continue
                    
                    # Write everything else as-is, except 'end' keyword
                    if line and line.lower() != 'end':
                        f.write(obj if obj.endswith('\n') else obj + '\n')
                    else:
                        f.write('\n')

            print(f"Created {tobj_path}")
            
            # Convert cfg file last
            cfg_path = os.path.join(output_dir, ogre_cfg)
            if os.path.exists(cfg_path):
                convert_cfg_to_otc(cfg_path)
                
            return True
            
        except IOError as e:
            print(f"Error creating files: {e}")
            return False
            
    except Exception as e:
        print(f"Error converting terrain: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python terrn_converter.py filename.terrn")
        sys.exit(1)
        
    success = convert_terrn_to_terrn2(sys.argv[1])
    if success:
        print("Terrain conversion completed successfully!")
    else:
        print("Terrain conversion failed!")
        sys.exit(1)
