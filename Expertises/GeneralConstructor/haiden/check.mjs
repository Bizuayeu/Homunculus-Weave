// 軽量チェックスクリプト（前捌き専用。バリデーションの権威は常にサーバ側 -- FR-4.1）
// 本尊: general-constructor (v0.3.0) / tool: judge_mokuromi
export function checkInput(input) {
	const required = ["housing_type","front_road_width","basement","existing_structure","land_price","land_location","ground_evaluation","effective_bcr","floors","units","max_far","effective_site_area","zoning"];
	const missing = required.filter((key) => input == null || input[key] === undefined);
	return { ok: missing.length === 0, missing };
}
