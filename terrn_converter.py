import os
import sys
import uuid

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
        terrain_name = os.path.splitext(os.path.basename(cfg_file))[0]
        
        with open(cfg_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line.startswith('#') or not line:
                    continue
                    
                if 'Heightmap.raw.size=' in line:
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
        
        if not all([heightmap_size, heightmap_bpp, world_size_x, world_size_z, max_height]):
            print("Error: Missing required values in cfg file")
            return False
            
        # Create .otc file
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
            f.write('MaxPixelError=0\n')
            f.write('LightmapEnabled=0\n')
            f.write('SpecularMappingEnabled=1\n')
            f.write('NormalMappingEnabled=1\n')
            
        print(f"Created {otc_path}")
        return True
        
    except Exception as e:
        print(f"Error converting cfg file: {e}")
        return False

def convert_terrn_to_terrn2(input_file):
    try:
        print(f"Converting {input_file} to terrn2 format...")
        
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

        # Create .tobj file
        tobj_name = os.path.splitext(ogre_cfg)[0] + ".tobj"
        output_dir = os.path.dirname(input_file)
        tobj_path = os.path.join(output_dir, tobj_name)
        
        try:
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
        except IOError as e:
            print(f"Error creating {tobj_path}: {e}")
            return False

        # Also convert the cfg file if it exists
        cfg_path = os.path.join(output_dir, ogre_cfg)
        if os.path.exists(cfg_path):
            convert_cfg_to_otc(cfg_path)

        # Create .terrn2 file
        output_name = os.path.splitext(input_file)[0] + '.terrn2'
        try:
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
            return True
        except IOError as e:
            print(f"Error creating {output_name}: {e}")
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
