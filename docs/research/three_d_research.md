# Image-to-3D in late 2026

## Leader for local use: TRELLIS.2 (Microsoft, MIT), native in ComfyUI since 0.34 (26 Aug 2026)
- **Sources:**
  - blog.comfy.org/p/trellis2-and-pixal3d-are-now-native
  - comfy.org/pixal3d-trellis2
  - huggingface.co/microsoft/TRELLIS.2-4B
  - book.st-hakky.com (VRAM guide)
- **What it makes:** a 4B-parameter model that produces a textured mesh with PBR materials (base colour, metallic, roughness).
  - ComfyUI's native pipeline re-implemented nvdiffrast/nvdiffrec, so it is commercially usable and needs no CUDA build step.
- **VRAM:** about 12 GB with the native int8 weights (upstream needs about 24 GB).
- **Published speeds on an H100:** 512³ ≈ 3 s, 1024³ ≈ 17 s, 1536³ ≈ 60 s. An RTX PRO 6000 Blackwell should be in the same range. We have not measured it.
- **Weaknesses:**
  - The raw mesh can have small holes. The template's `RemeshMesh(sign_mode=solid)` closes them.
  - The Comfy blog says closed services (Tripo, Rodin, Hunyuan 3D 3.x online) still look better.
  - Thin parts (hair strands, fingers) are soft.
  - Back views are invented.
- **Template:** `3d_pixal3d_trellis2_image_to_model.json`. Easy Studio uses its TRELLIS.2 branch (the switch set to TRELLIS.2), pruned to the nodes listed below.
- **Pipeline:**
  - Input: LoadImage → BiRefNet cut-out → ImageCropToMask(1024, pad 1.0) → Trellis2Conditioning(DINOv3).
  - Structure: EmptyTrellis2LatentStructure → KSampler(12, cfg 7.5) → VaeDecodeStructureTrellis2(32).
  - Shape: Trellis2ShapeStage → KSampler(20) → Trellis2UpsampleStage(1024 or 1536) → KSampler(12) → VaeDecodeShapeTrellis.
  - Texture: Trellis2TextureStage → KSampler(12, cfg 1) → VaeDecodeTextureTrellis.
  - Mesh cleanup: RemeshMesh(768, solid) → DecimateMesh(target faces) → MeshSmoothNormals → UnwrapMesh(pec, 2048).
  - Baking: BakeTextureFromVoxel(2048) + BakeNormalMapFromMesh → ApplyTextureToMesh.
  - Output: MeshToFile3D → **SaveGLB**.
- **Easy Studio quality presets:**
  - "Game-ready": 50k faces, 1024 detail, 1024 texture.
  - "Standard": 200k faces, 1024, 2048.
  - "Max detail": 700k faces, 1536, 2048. These are the template defaults.

## Backup: Hunyuan3D 2.1 (Tencent) — shape only in native ComfyUI
- Native nodes are Hunyuan3Dv2Conditioning, EmptyLatentHunyuan3Dv2, VAEDecodeHunyuan3D and VoxelToMesh. They give **untextured** "clay" geometry.
- It uses about 10 GB of VRAM for shape only. Texturing with Hunyuan's paint model needs custom nodes and about 29 GB.
- **Licence:** the Tencent Hunyuan 3D Community Licence excludes the EU, UK and South Korea. So it is **opt-in** (`--what 3d-shape`) and flagged as an open question.
- **Template:** `3d_hunyuan3d-v2.1.json` (30 steps, cfg 5, octree 256, surface net 0.6).

## Others looked at (not used)
- **Pixal3D** (also native): a TRELLIS.2 derivative with camera-aware (FOV via MoGe) conditioning, plus a multi-view variant. It's a possible Phase 3 "from multiple angles" upgrade, using our turnaround sheet as input.
- **Hosted services** (Meshy, Tripo, Rodin, Kaedim, CSM): cloud only. They are excluded because Easy Studio must stay private and local.

## Getting it into Blender / game engines
- **GLB** (binary glTF 2.0) carries the mesh, UVs and PBR textures in one file.
  - Blender: File → Import → glTF 2.0 (.glb/.gltf). It's built in, with no add-on.
  - Unity: install the glTFast package. Unreal: the built-in glTF importer. Godot: drag in the .glb.
- **No skeleton/rig.** For animation, rig it in Blender (Rigify), Mixamo (upload as FBX) or AccuRIG. That's a Phase 3 idea.
- **Viewer in Easy Studio:** Google's `<model-viewer>` web component, bundled locally as `app/static/vendor/model-viewer.min.js` (Apache-2.0).
  - Features: orbit/zoom, auto-rotate and an environment-lit preview, with no internet needed.
  - ComfyUI's own Preview3D/Load3D nodes are an alternative inside ComfyUI.
