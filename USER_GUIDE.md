# H3 Story Director 2.1.1

Separate node pack and workflow; v1 is preserved. Designed for revising existing shots in an edited movie.

On the test pod, open **14_Mara_Hotel_v2_Review.json** for the completed movie: all eight clips are pinned, clip 5 has two takes, and nothing is selected to rerender. **13_H3_Story_Director_v2.json** is the starting workflow.

## Use

1. Open `13_H3_Story_Director_v2.json`. Choose your character/location images in the main H3 picker. Match reference notes to picture order.
2. Enter story, style, target seconds and maximum clips. Choose **Plan only** and queue. Generated JSON is automatically saved in the node; no manual copy step.
3. Click **Open shot dashboard**. Review the table, edit prompts/sound/durations, and tick the shots to generate.
4. **Render selected + assemble** saves edits and queues. **Save edits** only saves into the workflow; Queue afterward. Save the workflow itself to carry your edits elsewhere.
5. Clips appear individually as they finish and remain saved if a later clip fails. Open the dashboard again after a reload to recover completed clips. **Recover saved project plan** explicitly loads the last executed plan from disk; save your unqueued edits before using it.
6. To repair a location jump in clip 5: select frame mode on clip 5, click **Previous clip → last frame**, tick only clip 5, then render. The other clips use their pinned saved takes.

In the dashboard, editing a field ticks that shot. Unticking it deliberately keeps its selected saved video; prompt changes are not applied until a render. The render button increases the Take number for selected clips; simply Queue after Save edits reuses an identical cached take. The dropdown under a clip restores a previous saved video. Different-duration takes require matching the duration field. Output files are never overwritten.

## Frame and reference controls

- In reference mode, **Previous clip → last frame as reference** appends the previous selected take’s final frame, keeping inherited character/location pictures and adding its picture mapping. You can also choose any saved clip and its first or last frame. The PNG is pinned, and the destination shot is selected for rerendering. This is visual guidance, not a locked opening frame.
- Reference mode uses the Fantastic H3 character/location stack. Copy the main references and replace individual pictures, or upload a separate per-shot picture list. Update the reference mapping when changing image order. An override replaces the entire main picture list for that shot; RefMods remain shared.
- Frame mode uses the FL2VA model with a first frame, a last frame, or both. Character/location references and RefMods are not fed to this mode. Describe the intended action plainly; keyframes supply visual context.
- Previous-last / next-first extracts a PNG from a completed saved take. It is pinned to that exact take. Changing the neighbor later does not silently replace the PNG; click the extraction button again to update it.
- Uploaded PNG/JPEG images can also serve as endpoints. The model may still change geometry after the initial frame; anchoring is not a guarantee of a perfect action or match.
- Clips are 5–15 seconds at 24 fps. Last-frame-conditioned clips preserve the decoded endpoint when conforming the model's frame grid to the requested duration. This may skip some intermediate frames; generated audio is trimmed to duration, not retimed. Assess audio/visual synchronization on these retakes.

## Saved data

`output/h3_story_director_v2/<project>/clips/` holds MP4s plus render metadata. `dashboard.json` is updated after every completed clip and retains take history. `latest_plan.json` contains the last executed plan. `latest_edit.json` and immutable hashed edit manifests describe completed assemblies. Final movies are saved by the visible SaveVideo node.

Keep a different project name for unrelated movies. Copy input assets, output project folders and workflow together to move a project to another machine. Plan-only doesn't load H3. There is no mid-sampling resume; only completed clips can be reused.

## Install

See [README.md](README.md) for repository installation instructions.

## Install from GitHub

Clone this repository into `ComfyUI/custom_nodes`, then use the same Python environment as ComfyUI:

```sh
python -m pip install -r requirements.txt
```

Restart ComfyUI and refresh the browser. This does not install PyTorch or change its CUDA build. Use a current ComfyUI with native MiniMax H3 support (tested: 0.39.0).

Story Director requires the Fantastic MiniMax H3 PromptBuilder pack, native H3 models/VAEs/text encoder, and the local Qwen3-4B-Instruct-2507 writer for automatic planning. Manual edited plans do not need the writer. The RunPod 0.23 installer installs these nodes and downloads the writer when H3 is enabled. Model weights are not included.

## Endangered AI

[Patreon](https://www.patreon.com/endangeredai) · [YouTube](https://www.youtube.com/@endangeredai) · [Website](https://endangeredai.com/)
