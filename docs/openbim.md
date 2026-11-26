# Send a CFS design to Steltic openBIM India

Install [Steltic openBIM India](https://github.com/Steltic/steltic_openBIM_india) in the same Python environment when exporting a physical steel layout. The native analysis can run independently.

Supply the building's design handoff geometry in millimetres. The project ID must match the native job name and the module must be `CFS`. Include grids, levels, member axes and section orientations, materials, panel boundaries and any located connection details. The [India exchange interface](https://github.com/Steltic/steltic_openBIM_india) describes these fields.

For each analysed occurrence put `native_ref` on the member. Choose `cfs:<member id>` from the job's `cfs_members` or `hr:<member id>` from `lateral_frame.members`. Supply the native material grade and, optionally, its effective `fy_mpa`. The exporter binds the selected profile, ply count, thickness-dependent design yield and check to each occurrence. It resolves metric section geometry against the native catalogues and rejects a conflicting profile override. A supplemental member requires an explicit profile and a review check.

For a connection, `connection:<id>` binds a CFS connection and `hr-connection:<id>` binds a hot-rolled connection. Declare the actual location, connecting members and any physical parts. The native status and hashes of the calculation package and available reports accompany the exchange.

With a layout already prepared, set `cfg["openbim_layout"] = layout` before calling `pipeline.design_and_report`. If automatic sizing is enabled, you can bind the final schedule after analysis.

```python
from openbim_handoff import write_handoff

handoff_file = write_handoff(job_directory, layout)
```

The exporter writes `design/openbim_handoff.json` and rejects unknown record IDs, conflicting member sections or invalid geometry.
