import pcbnew
import re
import datetime
import os


# === Global configuration ===
BUILD = "105"            # Build number
workDir = "stencil"      # Working folder name
min_mask_width = 0.22    # Minimum mask width (mm) between pads
pcbClearence = 0.1       # PCB clearance (mm) - moves outline outward from Edge.Cuts


class StencilGenerator(pcbnew.ActionPlugin):
    def defaults(self):
        self.name = "3DP Stencil Generator"
        self.category = "Modify PCB"
        self.description = "Generate OpenSCAD file for 3D printable solder stencil with alignment holes"
        self.show_toolbar_button = True
        self.icon_file_name = os.path.join(
            os.path.dirname(__file__), "./icon.png")

    def Run(self):
        try:
            board = pcbnew.GetBoard()
            project_file = board.GetFileName()
    
            if not project_file:
                raise RuntimeError("Geen board-bestand geladen")
    
            project_dir = os.path.dirname(project_file)
            output_dir = os.path.join(project_dir, workDir)
            os.makedirs(output_dir, exist_ok=True)
    
            log_file = os.path.join(output_dir, "kicad_stencilgen_debug.log")
   
            def log(msg):
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(f"{datetime.datetime.now()} - {msg}\n")
    
            log(f"===== Plugin gestart - BUILD {BUILD} =====")
            log(f"Project directory: {project_dir}")
    
            base_filename = re.sub(r'\.[^.]*$', '', os.path.basename(project_file))
            output_filename = os.path.join(output_dir, f"{base_filename}_stencil.scad")
    
            with open(output_filename, 'w', encoding='utf-8') as f:
                f.write(self.generate_openscad(board))
                log(f"SCAD-bestand geschreven: {output_filename}")
    
            pcbnew.Refresh()
            print(f"OpenSCAD file generated: {output_filename}")
            log("Script succesvol afgerond")
    
        except Exception as e:
            msg = f"FOUT in Run(): {repr(e)}"
            try:
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(f"{datetime.datetime.now()} - {msg}\n")
            except:
                print("Fout bij schrijven van logbestand.")
            print(msg)

    def generate_openscad(self, board):
        scad = "// KiCad Stencil Generator\n"
        scad += f"// Generated on {datetime.datetime.now()}\n\n"

        scad += "// Parameters (adjust as needed)\n"
        scad += "stencil_thickness = 0.2;  // mm (Thickness of the stencil)\n"
        scad += "frame_height = 2.0;       // mm (Height of the frame)\n"
        scad += "pcb_thickness = 1.6;      // mm (Thickness of the PCB)\n"
        scad += "alignment_pin_diameter = 3.0;  // mm (Diameter of alignment holes)\n"
        scad += "\n"
        scad += "// Feature toggle\n"
        scad += "enable_alignment_holes = true;\n"
        scad += "\n"
        scad += "$fs = 0.1;  // Set minimum facet size for curves\n"
        scad += "$fa = 5;    // Set minimum angle for facets\n\n"

        scad += self.generate_modules(board)

        scad += "union(){\n"
        scad += "stencil();\n"
        scad += "        if (enable_alignment_holes) alignment_holes();\n}"

        return scad

    def generate_modules(self, board):
        scad = "module frame() {\n"
        scad += self.generate_frame(board)
        scad += "}\n\n"

        scad += "module pcb_outline() {\n"
        scad += self.generate_pcb_outline(board)
        scad += "}\n\n"

        scad += "module pads() {\n"
        scad += self.generate_pads(board)
        scad += "}\n\n"

        scad += "module alignment_holes() {\n"
        scad += self.generate_alignment_holes(board)
        scad += "}\n\n"

        scad += "module stencil() {\n"
        scad += "    difference() {\n"
        scad += "        frame();\n"
        scad += "        translate([0, 0, frame_height - pcb_thickness]) {\n"
        scad += "            linear_extrude(height=pcb_thickness + 0.01) {\n"
        scad += "                pcb_outline();\n"
        scad += "            }\n"
        scad += "        }\n"
        scad += "        translate([0, 0, - stencil_thickness]) {\n"
        scad += "            linear_extrude(height=frame_height + stencil_thickness) {\n"
        scad += "                pads();\n"
        scad += "            }\n"
        scad += "        }\n"
        scad += "    }\n"
        scad += "}\n\n"

        return scad

    def generate_frame(self, board):
        frame_rect = self.find_shape_on_layer(board, pcbnew.User_8)
        if not frame_rect:
            return "    // No frame found on User.8 layer\n"

        scad = f"    linear_extrude(height=frame_height) {{\n"
        scad += f"        square([{self.mm(frame_rect[2])}, {self.mm(frame_rect[3])}], center=true);\n"
        scad += "    }\n"
        return scad
    
    def connect_line_segments(self, segments):
        """Try to connect line segments into a closed polygon"""
        if not segments:
            return []
        
        # Start with the first segment
        polygon = list(segments[0])
        used_segments = {0}
        
        tolerance = 0.01  # mm tolerance for connecting points
        
        while len(used_segments) < len(segments):
            last_point = polygon[-1]
            found_connection = False
            
            # Look for a segment that connects to the last point
            for i, segment in enumerate(segments):
                if i in used_segments:
                    continue
                    
                start, end = segment
                
                # Check if segment start connects to last point
                if self.points_close(last_point, start, tolerance):
                    polygon.append(end)
                    used_segments.add(i)
                    found_connection = True
                    break
                # Check if segment end connects to last point
                elif self.points_close(last_point, end, tolerance):
                    polygon.append(start)
                    used_segments.add(i)
                    found_connection = True
                    break
            
            if not found_connection:
                # Can't connect more segments
                break
        
        # Check if we have a closed polygon (last point connects to first)
        if len(polygon) > 2 and self.points_close(polygon[-1], polygon[0], tolerance):
            polygon.pop()  # Remove duplicate closing point
            return polygon
        
        # If not closed or too few segments used, return empty
        if len(used_segments) < len(segments) * 0.8:  # At least 80% of segments should be used
            return []
        
        return polygon

    def points_close(self, p1, p2, tolerance):
        """Check if two points are within tolerance distance"""
        return abs(p1[0] - p2[0]) < tolerance and abs(p1[1] - p2[1]) < tolerance

    def mm(self, nm):
        return nm / 1e6

    def generate_pcb_outline_from_edge_cuts(self, board):
      """Generate PCB outline from Edge.Cuts layer as a single polygon or union of shapes"""
      
      log = getattr(self, 'log_function', lambda msg: print(f"DEBUG: {msg}"))
      
      log("=== Starting Edge.Cuts analysis ===")
      
      # Get PCB bounding box for centering
      pcb_rect = self.find_shape_on_layer(board, pcbnew.User_9)
      if pcb_rect:
          center_x = pcb_rect[0] + pcb_rect[2]/2
          center_y = pcb_rect[1] + pcb_rect[3]/2
          log(f"Using User.9 center: ({self.mm(center_x)}, {self.mm(center_y)}) mm")
      else:
          bbox = board.GetBoundingBox()
          center_x = bbox.GetCenter().x
          center_y = bbox.GetCenter().y
          log(f"Using board bbox center: ({self.mm(center_x)}, {self.mm(center_y)}) mm")
      
      # Collect all Edge.Cuts elements
      shapes = []
      line_segments = []
      
      for drawing in board.GetDrawings():
          if drawing.GetLayer() == pcbnew.Edge_Cuts and isinstance(drawing, pcbnew.PCB_SHAPE):
              shape_type = drawing.GetShape()
              
              if shape_type == pcbnew.SHAPE_T_SEGMENT:
                  # Collect line segments to form polygon
                  start = drawing.GetStart()
                  end = drawing.GetEnd()
                  x1, y1 = self.mm(start.x - center_x), self.mm(start.y - center_y)
                  x2, y2 = self.mm(end.x - center_x), self.mm(end.y - center_y)
                  line_segments.append([(x1, y1), (x2, y2)])
                  log(f"Line segment: ({x1}, {y1}) to ({x2}, {y2})")
                  
              elif shape_type == pcbnew.SHAPE_T_CIRCLE:
                  # Add circle as separate shape
                  center_circle = drawing.GetCenter()
                  radius = drawing.GetRadius()
                  cx, cy = self.mm(center_circle.x - center_x), self.mm(center_circle.y - center_y)
                  r = self.mm(radius)
                  shapes.append(f"translate([{cx}, {cy}]) circle(r={r})")
                  log(f"Circle: center ({cx}, {cy}), radius {r}")
                  
              elif shape_type == pcbnew.SHAPE_T_RECT:
                  # Add rectangle as separate shape
                  start = drawing.GetStart()
                  end = drawing.GetEnd()
                  x1, y1 = self.mm(start.x - center_x), self.mm(start.y - center_y)
                  x2, y2 = self.mm(end.x - center_x), self.mm(end.y - center_y)
                  w, h = abs(x2 - x1), abs(y2 - y1)
                  cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
                  shapes.append(f"translate([{cx}, {cy}]) square([{w}, {h}], center=true)")
                  log(f"Rectangle: center ({cx}, {cy}), size {w}x{h}")
                  
              elif shape_type == pcbnew.SHAPE_T_ARC:
                  # Convert arc to polygon approximation
                  center_arc = drawing.GetCenter()
                  start = drawing.GetStart()
                  end = drawing.GetEnd()
                  
                  # Calculate arc parameters
                  cx, cy = self.mm(center_arc.x - center_x), self.mm(center_arc.y - center_y)
                  sx, sy = self.mm(start.x - center_x), self.mm(start.y - center_y)
                  ex, ey = self.mm(end.x - center_x), self.mm(end.y - center_y)
                  
                  # Calculate radius and angles
                  import math
                  radius = math.sqrt((sx - cx)**2 + (sy - cy)**2)
                  start_angle = math.atan2(sy - cy, sx - cx)
                  end_angle = math.atan2(ey - cy, ex - cx)
                  
                  # Generate arc points (approximate with line segments)
                  arc_points = []
                  num_segments = max(8, int(abs(end_angle - start_angle) * 180 / math.pi / 10))
                  
                  if end_angle < start_angle:
                      end_angle += 2 * math.pi
                      
                  for i in range(num_segments + 1):
                      angle = start_angle + (end_angle - start_angle) * i / num_segments
                      x = cx + radius * math.cos(angle)
                      y = cy + radius * math.sin(angle)
                      arc_points.append((x, y))
                  
                  # Add arc points to line segments
                  for i in range(len(arc_points) - 1):
                      line_segments.append([arc_points[i], arc_points[i + 1]])
                  
                  log(f"Arc: center ({cx}, {cy}), radius {radius}, {num_segments} segments")
      
      # Build the final SCAD code
      scad = ""
      
      # If we have line segments, try to form a closed polygon
      if line_segments:
          polygon_points = self.connect_line_segments(line_segments)
          if polygon_points:
              points_str = ",".join([f"[{x},{y}]" for x, y in polygon_points])
              scad += f"    polygon(points=[{points_str}]);\n"
              log(f"Created polygon with {len(polygon_points)} points")
          else:
              # If we can't form a closed polygon, create individual line shapes
              log("Could not form closed polygon, using individual line shapes")
              for segment in line_segments:
                  (x1, y1), (x2, y2) = segment
                  # Create a thin rectangle for each line segment
                  length = ((x2-x1)**2 + (y2-y1)**2)**0.5
                  if length > 0.001:  # Avoid zero-length segments
                      angle = math.atan2(y2-y1, x2-x1) * 180 / math.pi
                      cx, cy = (x1+x2)/2, (y1+y2)/2
                      shapes.append(f"translate([{cx}, {cy}]) rotate([0, 0, {angle}]) square([{length}, 0.1], center=true)")
      
      # Add other shapes to union if we have any
      if shapes:
          if scad:  # We already have a polygon
              scad = f"    union() {{\n        polygon(points=[{points_str}]);\n"
              for shape in shapes:
                  scad += f"        {shape};\n"
              scad += "    }\n"
          else:  # Only shapes, no polygon
              if len(shapes) == 1:
                  scad = f"    {shapes[0]};\n"
              else:
                  scad = "    union() {\n"
                  for shape in shapes:
                      scad += f"        {shape};\n"
                  scad += "    }\n"
      
      # Fallback if no Edge.Cuts found
      if not scad:
          log("No Edge.Cuts shapes found, using board bounding box fallback")
          bbox = board.GetBoundingBox()
          w = self.mm(bbox.GetWidth())
          h = self.mm(bbox.GetHeight())
          scad = f"    square([{w}, {h}], center=true);\n"
          log(f"Fallback size: {w} x {h} mm")
      
      log("=== Edge.Cuts analysis complete ===")
   
      return scad


    def generate_pcb_outline(self, board):
        log = getattr(self, 'log_function', lambda msg: print(f"DEBUG: {msg}"))
        self.debug_all_layers(board)
        pcb_rect = self.find_shape_on_layer(board, pcbnew.User_9)
        if pcb_rect:
            log("Using User.9 rectangle for PCB outline")
            scad = f"    square([{self.mm(pcb_rect[2])}, {self.mm(pcb_rect[3])}], center=true);\n"
            return scad
        else:
            log("No User.9 rectangle found, falling back to Edge.Cuts")
            return self.generate_pcb_outline_from_edge_cuts(board)


    def get_pad_bounds(self, pad_info):
        """Get the bounding box of a pad considering its rotation"""
        import math
        
        angle_rad = math.radians(pad_info['angle'])
        half_w = pad_info['width'] / 2
        half_h = pad_info['height'] / 2
        
        # Calculate rotated corner positions
        corners = [
            (-half_w, -half_h),
            (half_w, -half_h),
            (half_w, half_h),
            (-half_w, half_h)
        ]
        
        rotated_corners = []
        for x, y in corners:
            rx = x * math.cos(angle_rad) - y * math.sin(angle_rad)
            ry = x * math.sin(angle_rad) + y * math.cos(angle_rad)
            rotated_corners.append((rx + pad_info['x'], ry + pad_info['y']))
        
        min_x = min(corner[0] for corner in rotated_corners)
        max_x = max(corner[0] for corner in rotated_corners)
        min_y = min(corner[1] for corner in rotated_corners)
        max_y = max(corner[1] for corner in rotated_corners)
        
        return {
            'min_x': min_x,
            'max_x': max_x,
            'min_y': min_y,
            'max_y': max_y,
            'width': max_x - min_x,
            'height': max_y - min_y
        }

    def find_close_pads(self, current_pad, all_pads, current_index, search_radius):
        """Find pads within search_radius of the current pad"""
        import math
        
        close_pads = []
        current_x = current_pad['x']
        current_y = current_pad['y']
        
        for i, pad in enumerate(all_pads):
            if i == current_index:
                continue
                
            dx = pad['x'] - current_x
            dy = pad['y'] - current_y
            distance = math.sqrt(dx*dx + dy*dy)
            
            if distance <= search_radius:
                close_pads.append(pad)
        
        return close_pads


    def project_pad_dimension(self, pad_info, direction_x, direction_y):
        """Project pad's half-dimension onto a given direction"""
        import math
        
        angle_rad = math.radians(pad_info['angle'])
        half_w = pad_info['width'] / 2
        half_h = pad_info['height'] / 2
        
        # Pad's local axes in global coordinates
        pad_x_axis = (math.cos(angle_rad), math.sin(angle_rad))
        pad_y_axis = (-math.sin(angle_rad), math.cos(angle_rad))
        
        # Project pad dimensions onto the given direction
        proj_x = abs(half_w * (pad_x_axis[0] * direction_x + pad_x_axis[1] * direction_y))
        proj_y = abs(half_h * (pad_y_axis[0] * direction_x + pad_y_axis[1] * direction_y))
        
        return proj_x + proj_y


    def calculate_mask_constrained_pad(self, current_pad, all_pads, current_index):
        """Calculate pad dimensions constrained by minimum mask width"""
        import math
        
        adjusted_pad = current_pad.copy()
        
        # Find nearby pads that might require mask constraints
        nearby_pads = self.find_close_pads(current_pad, all_pads, current_index, min_mask_width * 3)
        
        if not nearby_pads:
            return adjusted_pad
        
        # For each nearby pad, check if we need to constrain the current pad
        for nearby_pad in nearby_pads:
            # Calculate distance between pad centers
            dx = nearby_pad['x'] - current_pad['x']
            dy = nearby_pad['y'] - current_pad['y']
            distance = math.sqrt(dx*dx + dy*dy)
            
            if distance < 0.001:  # Skip if pads are at same position
                continue
                
            # Calculate the minimum required distance between pad edges
            # This is the sum of half-widths plus minimum mask width
            current_bounds = self.get_pad_bounds(current_pad)
            nearby_bounds = self.get_pad_bounds(nearby_pad)
            
            # Calculate required separation in the direction between centers
            direction_x = dx / distance
            direction_y = dy / distance
            
            # Project pad half-dimensions onto the line between centers
            current_half_proj = self.project_pad_dimension(current_pad, direction_x, direction_y)
            nearby_half_proj = self.project_pad_dimension(nearby_pad, -direction_x, -direction_y)
            
            required_distance = current_half_proj + nearby_half_proj + min_mask_width
            
            if distance < required_distance:
                # Need to shrink current pad
                shrink_amount = (required_distance - distance) / 2
                
                # Determine which dimension to shrink based on pad orientation and direction
                angle_rad = math.radians(current_pad['angle'])
                
                # Transform direction to pad's local coordinate system
                local_dir_x = direction_x * math.cos(-angle_rad) - direction_y * math.sin(-angle_rad)
                local_dir_y = direction_x * math.sin(-angle_rad) + direction_y * math.cos(-angle_rad)
                
                # Shrink the dimension that's most aligned with the direction to nearby pad
                if abs(local_dir_x) > abs(local_dir_y):
                    # Shrink width
                    new_width = max(0.1, adjusted_pad['width'] - shrink_amount * 2)
                    adjusted_pad['width'] = new_width
                else:
                    # Shrink height
                    new_height = max(0.1, adjusted_pad['height'] - shrink_amount * 2)
                    adjusted_pad['height'] = new_height
        
        return adjusted_pad


    def generate_pads(self, board):
        scad = ""
        
        # Try to get center from User.9 first
        pcb_rect = self.find_shape_on_layer(board, pcbnew.User_9)
        if pcb_rect:
            center_x = pcb_rect[0] + pcb_rect[2]/2
            center_y = pcb_rect[1] + pcb_rect[3]/2
        else:
            # Fallback to board bounding box center
            bbox = board.GetBoundingBox()
            center_x = bbox.GetCenter().x
            center_y = bbox.GetCenter().y

        # Collect all SMD pads with their information
        pads_info = []
        for module in board.GetFootprints():
            for pad in module.Pads():
                if pad.GetAttribute() == pcbnew.PAD_ATTRIB_SMD:
                    pos = pad.GetPosition()
                    size = pad.GetSize()
                    angle = pad.GetOrientation().AsDegrees()
                    pads_info.append({
                        'x': self.mm(pos.x - center_x),
                        'y': self.mm(pos.y - center_y),
                        'width': self.mm(size.x),
                        'height': self.mm(size.y),
                        'angle': angle,
                        'pad': pad
                    })

        # Generate pad cutouts with mask constraints
        for i, pad_info in enumerate(pads_info):
            adjusted_pad = self.calculate_mask_constrained_pad(pad_info, pads_info, i)
            
            scad += f"    translate([{adjusted_pad['x']}, {adjusted_pad['y']}]) "
            scad += f"rotate([0, 0, {adjusted_pad['angle']}]) "
            scad += f"square([{adjusted_pad['width']}, {adjusted_pad['height']}], center=true);\n"
        
        if not scad:
            scad = "    // No SMD pads found\n"
        
        return scad

    def generate_alignment_holes(self, board):
        alignment_holes = self.find_circles_on_layer(board, pcbnew.User_7)
        if not alignment_holes:
            return "    // No alignment holes found on User.7 layer\n"

        pcb_rect = self.find_shape_on_layer(board, pcbnew.User_9)
        if not pcb_rect:
            return "    // No PCB outline found on User.9 layer\n"

        center_x = pcb_rect[0] + pcb_rect[2]/2
        center_y = pcb_rect[1] + pcb_rect[3]/2

        scad = ""
        for hole in alignment_holes:
            x = self.mm(hole[0] - center_x)
            y = self.mm(hole[1] - center_y)
            scad += f"    translate([{x}, {y}, -0.005]) "
            scad += f"cylinder(h=frame_height + 0.01, d=alignment_pin_diameter, center=false);\n"
        return scad

    def find_shape_on_layer(self, board, layer):
        for drawing in board.GetDrawings():
            if (isinstance(drawing, pcbnew.PCB_SHAPE) and
                drawing.GetShape() == pcbnew.SHAPE_T_RECT and
                    drawing.GetLayer() == layer):
                return (drawing.GetStart().x, drawing.GetStart().y,
                        drawing.GetEnd().x - drawing.GetStart().x,
                        drawing.GetEnd().y - drawing.GetStart().y)
        return None

    def find_circles_on_layer(self, board, layer):
        circles = []
        for drawing in board.GetDrawings():
            if (isinstance(drawing, pcbnew.PCB_SHAPE) and
                drawing.GetShape() == pcbnew.SHAPE_T_CIRCLE and
                    drawing.GetLayer() == layer):
                center = drawing.GetCenter()
                circles.append((center.x, center.y))
        return circles

    def mm(self, nm):
        return nm / 1e6

    def debug_all_layers(self, board):
        """Debug function to list all layers with drawings"""
        try:
            project_file = board.GetFileName()
            project_dir = os.path.dirname(project_file)
            output_dir = os.path.join(project_dir, workDir)
            log_file = os.path.join(output_dir, "all_layers_debug.log")
            
            with open(log_file, "w", encoding="utf-8") as f:
                f.write(f"=== All Layers Analysis ===\n")
                
                layer_counts = {}
                for drawing in board.GetDrawings():
                    layer = drawing.GetLayer()
                    if layer not in layer_counts:
                        layer_counts[layer] = 0
                    layer_counts[layer] += 1
                
                f.write(f"Total drawings: {sum(layer_counts.values())}\n")
                for layer, count in sorted(layer_counts.items()):
                    f.write(f"Layer {layer}: {count} drawings\n")
                    
                f.write(f"\nEdge_Cuts constant value: {pcbnew.Edge_Cuts}\n")
        except Exception as e:
            print(f"Debug error: {e}")


StencilGenerator().register()
