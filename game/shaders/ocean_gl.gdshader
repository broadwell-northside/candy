shader_type spatial;
render_mode cull_disabled, diffuse_lambert, specular_schlick_ggx;

uniform vec3 deep_color : source_color = vec3(0.04, 0.22, 0.34);
uniform vec3 shallow_color : source_color = vec3(0.22, 0.55, 0.62);
uniform vec3 foam_color : source_color = vec3(0.93, 0.90, 0.82);
uniform float shore_z = 1.1;
uniform float foam_width = 1.35;

varying vec3 world_pos;

void vertex() {
	vec3 point = VERTEX;
	point.y += sin(point.x * 0.35 + TIME * 1.1) * 0.06;
	point.y += sin(point.z * 0.22 + TIME * 0.7) * 0.04;
	VERTEX = point;
	world_pos = (MODEL_MATRIX * vec4(point, 1.0)).xyz;
}

void fragment() {
	float along = sin(world_pos.x * 0.65 + TIME * 1.3);
	float edge = world_pos.z - shore_z;
	float foam = smoothstep(foam_width, 0.05, abs(edge - along * 0.35));
	foam *= 0.45 + 0.55 * smoothstep(-0.2, 0.8, along);
	vec3 water = mix(deep_color, shallow_color, smoothstep(-18.0, shore_z, world_pos.z));
	ALBEDO = mix(water, foam_color, clamp(foam, 0.0, 1.0));
	ROUGHNESS = mix(0.22, 0.7, foam);
	METALLIC = 0.0;
	SPECULAR = 0.3;
}
