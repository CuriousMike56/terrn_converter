import os
import sys
import uuid

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
    alpha1_mask = [1,1,1,0]  # Default mask
    
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
                # Create page file with custom material textures
                page_path = os.path.join(os.path.dirname(cfg_file), f'{terrain_name}-page-0-0.otc')
                with open(page_path, 'w') as f:
                    f.write(f'{terrain_name}.raw\n')
                    f.write(f'{len(material_textures["layers"])}\n')
                    f.write('; worldSize, diffusespecular, normalheight, blendmap, blendmapmode, alpha\n')
                    
                    # Write each texture layer with proper formatting
                    for i, (diffuse, normal) in enumerate(material_textures['layers']):
                        blend_idx = i // 3  # Which RGB map to use
                        rgb_channel = ['R', 'G', 'B'][i % 3]  # Which channel in the RGB map
                        
                        if blend_idx < len(material_textures['blendmaps']):
                            blendmap = material_textures['blendmaps'][blend_idx]
                            # Clean up texture names and remove any comments
                            diffuse = diffuse.split('//')[0].strip()
                            normal = normal.split('//')[0].strip()
                            blendmap = blendmap.split('//')[0].strip()
                            # Format with commas
                            f.write(f'6, {diffuse}, {normal}, {blendmap}, {rgb_channel}, 0.99\n')
                
                print(f"Created {page_path}")
                return True

        # Create page-0-0.otc file for simple terrain
        page_path = os.path.join(os.path.dirname(cfg_file), f'{terrain_name}-page-0-0.otc')
        with open(page_path, 'w') as f:
            # Write heightmap filename
            if heightmap_image:
                f.write(f'{heightmap_image}\n')
            else:
                f.write(f'{terrain_name}.raw\n')
                
            # Write number of texture layers
            f.write('2\n')
            
            # Write base layer
            if world_texture:
                base_name, ext = os.path.splitext(world_texture)
                base_texture = f"{base_name}_DS.dds"
            else:
                base_texture = f'{terrain_name}_DS.dds'
            f.write(f'; worldSize, diffusespecular, normalheight, blendmap, blendmapmode, alpha\n')
            f.write(f'{world_size_x}, {base_texture}, blank_NRM.dds\n')
            
            # Write detail layer
            f.write('10, terrain_detail_dark_ds.dds, terrain_detail_nrm.dds, terrain_detail_rgb.png, R, 0.8\n')

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
                    
                # First 5 lines are header info
                if not terrain_name:
                    terrain_name = line
                elif not ogre_cfg:
                    ogre_cfg = line
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
