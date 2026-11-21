shader_type spatial;
render_mode cull_disabled, diffuse_burley, specular_schlick_ggx;

uniform vec3 deep_color : source_color = vec3(0.03, 0.18, 0.32);
uniform vec3 shallow_color : source_color = vec3(0.25, 0.58, 0.64);
uniform vec3 foam_color : source_color = vec3(0.95, 0.91, 0.82);
uniform float shore_z = 1.1;
uniform float foam_width = 1.45;

varying vec3 world_pos;
varying vec3 world_normal;

void vertex() {
	vec3 point = VERTEX;
	float wave_x = sin(point.x * 0.35 + TIME * 1.15);
	float wave_z = sin(point.z * 0.22 + TIME * 0.75);
	point.y += wave_x * 0.09 + wave_z * 0.06;
	VERTEX = point;
	world_pos = (MODEL_MATRIX * vec4(point, 1.0)).xyz;
	float slope_x = cos(point.x * 0.35 + TIME * 1.15) * 0.35 * 0.09;
	float slope_z = cos(point.z * 0.22 + TIME * 0.75) * 0.22 * 0.06;
	vec3 normal = normalize(vec3(-slope_x, 1.0, -slope_z));
	world_normal = normalize((MODEL_MATRIX * vec4(normal, 0.0)).xyz);
}

void fragment() {
	float along = sin(world_pos.x * 0.7 + TIME * 1.4);
	float edge = world_pos.z - shore_z;
	float foam = smoothstep(foam_width, 0.04, abs(edge - along * 0.4));
	foam *= 0.35 + 0.65 * smoothstep(-0.15, 0.85, along);
	vec3 water = mix(deep_color, shallow_color, smoothstep(-20.0, shore_z, world_pos.z));
	ALBEDO = mix(water, foam_color, clamp(foam, 0.0, 1.0));
	ROUGHNESS = mix(0.045, 0.48, foam);
	METALLIC = 0.0;
	SPECULAR = 0.72;
	NORMAL = normalize((VIEW_MATRIX * vec4(world_normal, 0.0)).xyz);
}
