# ULTRA GRAPHICS GUIDE

## What actually improves graphics

Line count is not a rendering feature. The biggest visual gains come from:

1. Better geometry and silhouettes.
2. Correct surface normals.
3. PBR materials.
4. Normal, roughness and metallic texture maps.
5. High quality character and vehicle assets.
6. Shadows and good lighting placement.
7. Atmosphere, fog, sky and weather.
8. Post processing and tone mapping.
9. Animation quality.
10. Level-art composition.

This ULTRA build improves items 2, 3, 6, 7 and parts of 8 while keeping all content generated in code.

## Quality tiers

LOW is intended for weak hardware.
MEDIUM reduces scene density.
HIGH is the practical default for many PCs.
ULTRA is the default for the project.
CINEMATIC enables the highest shadow and environment budgets.

## Where to add real assets later

Create an `assets/models` folder and load `.glb` files through Panda3D's model loader. Keep procedural shapes as collision proxies or fallbacks.

Recommended replacements in order:

1. FPS weapon and hands.
2. Street Rush player car and traffic cars.
3. Zombie character meshes and animations.
4. Runner character.
5. Buildings and road props.
6. Space ships.

## Material workflow

Use glTF 2.0 assets with physically based metallic/roughness materials. This project already initializes a PBR pipeline when the dependency is available. Textured assets will produce a much bigger fidelity improvement than adding tens of thousands of Python lines.
