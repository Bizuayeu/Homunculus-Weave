// 軽量チェックスクリプト（前捌き専用。バリデーションの権威は常にサーバ側 -- FR-4.1）
// 本尊: general-constructor (v0.3.0) / tool: judge_mokuromi
export function checkInput(input) {
	const required = ["住宅種別","前面道路幅員","半地下有無","古家構造","土地価格","土地所在","地盤評価","実効建蔽率","建物層数","戸数","最大容積率","有効宅地面積","用途地域"];
	const missing = required.filter((key) => input == null || input[key] === undefined);
	return { ok: missing.length === 0, missing };
}
