import type { CropProfileRead } from "../types/ranking";

interface CropSelectorProps {
  crops: CropProfileRead[];
  selectedCropId: number | null;
  disabled?: boolean;
  onChange: (cropId: number) => void;
}

export function CropSelector({
  crops,
  selectedCropId,
  disabled = false,
  onChange,
}: CropSelectorProps) {
  return (
    <label className="control">
      <span className="control__label">Select crop</span>
      <select
        className="control__input"
        disabled={disabled || crops.length === 0}
        value={selectedCropId ?? ""}
        onChange={(event) => onChange(Number(event.target.value))}
      >
        <option value="" disabled>
          Choose a crop profile
        </option>
        {crops.map((crop) => (
          <option key={crop.id} value={crop.id}>
            {crop.crop_name}
            {crop.scientific_name ? ` · ${crop.scientific_name}` : ""}
          </option>
        ))}
      </select>
    </label>
  );
}
