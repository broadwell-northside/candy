shader_type spatial;
render_mode cull_disabled, diffuse_burley, specular_schlick_ggx, depth_draw_opaque;

uniform sampler2D albedo_tex : source_color, filter_linear_mipmap;
uniform sampler2D depth_tex : hint_default_white, filter_linear;
uniform float parallax_strength = 0.045;
uniform float breathing = 0.016;

void vertex() {
	float breath = sin(TIME * 1.5) * breathing;
	VERTEX.y += breath * smoothstep(0.22, 1.0, UV.y);
	VERTEX.x += sin(TIME * 0.7) * 0.007 * smoothstep(0.55, 1.0, UV.y);
	float chest = smoothstep(0.18, 0.5, UV.y) * (1.0 - smoothstep(0.72, 0.95, UV.y));
	chest *= 1.0 - abs(UV.x * 2.0 - 1.0);
	VERTEX.z += chest * 0.045;
}

void fragment() {
	float depth = texture(depth_tex, UV).r;
	vec3 view_dir = normalize(VIEW);
	vec2 uv = UV + view_dir.xy * (depth - 0.35) * parallax_strength;
	uv = clamp(uv, vec2(0.002), vec2(0.998));
	vec4 tex = texture(albedo_tex, uv);
	if (tex.a < 0.45) {
		discard;
	}
	ALBEDO = tex.rgb;
	ALPHA = 1.0;
	ROUGHNESS = 0.72;
	METALLIC = 0.0;
}
