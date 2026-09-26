# Bystedts Cloth Builder 1.0.1

Author: **Daniel Bystedt**.

Official source: https://3dbystedt.gumroad.com/l/bystedtsClothBuilder

Author's tutorial: https://www.youtube.com/watch?v=EAraCGAaLoU

The user supplied this unmodified archive. SHA-256:
`132440c150ce09a04d5e7b19de57485cfcf0d630914fd63201c9835abca0dab8`.
The package's source header declares GPL-3.0-or-later; see `COPYING` and the
original source headers inside the ZIP. No paid feature or Tripo credit is used.

`blender/install_bystedts_cloth_builder.py` installs/enables this archive and
adds its asset library to Blender preferences. It was verified in Blender
5.2.1 LTS. Installation is separate from validation of an Alice garment.

Alice's new internal construction study appends only the author's Geometry
Nodes groups. It does not import the package's generic people or clothing.
`Post sim cloth` follows the Cloth modifier, with seam separation at zero and
inward thickness. The loaded UV storage node is adapted to `FLOAT2` for Blender
5.2 UV-layer recognition; the ZIP and vendor Python remain unchanged. Optional
legacy triangulation is disabled to retain the authored quad cloth cage.

The full Tripo exterior remains a separate complete object. The current inner
study has working thickness and automatic UVs but remains unfinished against
the photo: lace, natural gathers, remaining foundation garments, shared rig,
all actions and cloth collisions still require work.
