use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::collections::{BTreeMap, BTreeSet};

#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Bounds {
    pub min: [f64; 3],
    pub max: [f64; 3],
}

impl Bounds {
    fn dimensions(&self) -> [f64; 3] {
        std::array::from_fn(|i| self.max[i] - self.min[i])
    }
    fn center(&self) -> [f64; 3] {
        std::array::from_fn(|i| self.min[i] + (self.max[i] - self.min[i]) / 2.0)
    }
    fn distance(&self, other: &Self) -> f64 {
        (0..3)
            .map(|i| {
                (self.min[i] - other.max[i])
                    .max(other.min[i] - self.max[i])
                    .max(0.0)
                    .powi(2)
            })
            .sum::<f64>()
            .sqrt()
    }
}

#[derive(Clone, Debug, Default, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Mesh {
    pub vertices: u32,
    pub triangles: u32,
    pub connected_components: u32,
    pub non_manifold_edges: u32,
    pub degenerate_faces: u32,
    pub missing_material_faces: u32,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Object {
    pub id: String,
    pub kind: String,
    pub parent: Option<String>,
    pub semantic_role: Option<String>,
    pub world_matrix: [[f64; 4]; 4],
    pub bounds: Option<Bounds>,
    pub mesh: Option<Mesh>,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Connection {
    pub name: String,
    pub object_a: String,
    pub point_a: [f64; 3],
    pub object_b: String,
    pub point_b: [f64; 3],
    pub max_distance: f64,
}

#[derive(Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Scene {
    pub schema_version: String,
    pub source: String,
    pub blender_version: String,
    pub frame: i32,
    pub meters_per_unit: f64,
    pub limitations: Vec<String>,
    pub objects: Vec<Object>,
}

#[derive(Debug, Deserialize, Serialize)]
#[serde(default, deny_unknown_fields)]
pub struct Options {
    pub object_id: Option<String>,
    pub include_descendants: bool,
    pub offset: usize,
    pub limit: usize,
    pub proximity: f64,
    pub ground_z: Option<f64>,
    pub ground_objects: Vec<String>,
    pub contact_pairs: Vec<[String; 2]>,
    pub connection_points: Vec<Connection>,
    pub tolerance: f64,
    pub triangle_budget: Option<u64>,
    pub require_closed_mesh: bool,
}

impl Default for Options {
    fn default() -> Self {
        Self {
            object_id: None,
            include_descendants: true,
            offset: 0,
            limit: 40,
            proximity: 0.01,
            ground_z: None,
            ground_objects: vec![],
            contact_pairs: vec![],
            connection_points: vec![],
            tolerance: 0.001,
            triangle_budget: None,
            require_closed_mesh: false,
        }
    }
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Request {
    pub scene: Scene,
    #[serde(default)]
    pub options: Options,
}

fn validate(scene: &Scene, options: &Options) -> Result<(), String> {
    if scene.schema_version != "bas-scene-ir/0.1" {
        return Err("Unsupported SceneIR version".into());
    }
    if scene.objects.len() > 2048 {
        return Err("SceneIR exceeds 2048 objects".into());
    }
    if !(1..=200).contains(&options.limit) || options.offset > 2048 {
        return Err("Invalid pagination (limit 1..200, offset 0..2048)".into());
    }
    if !scene.meters_per_unit.is_finite() || scene.meters_per_unit <= 0.0 {
        return Err("Invalid unit scale".into());
    }
    for value in [options.proximity, options.tolerance] {
        if !value.is_finite() || !(0.0..=1e9).contains(&value) {
            return Err("Distances must be finite and between 0 and 1e9".into());
        }
    }
    if options
        .ground_z
        .is_some_and(|z| !z.is_finite() || z.abs() > 1e12)
        || (!options.ground_objects.is_empty() && options.ground_z.is_none())
    {
        return Err("Ground checks require a finite explicit ground_z".into());
    }
    if options.contact_pairs.len() > 200 {
        return Err("At most 200 contact pairs are allowed".into());
    }
    if options.connection_points.len() > 100 {
        return Err("At most 100 connection points are allowed".into());
    }
    let ids: BTreeMap<_, _> = scene.objects.iter().map(|o| (o.id.as_str(), o)).collect();
    if ids.len() != scene.objects.len() {
        return Err("Duplicate object IDs".into());
    }
    for object in &scene.objects {
        if object.id.is_empty()
            || object.id.len() > 1024
            || object.semantic_role.as_ref().is_some_and(|s| s.len() > 256)
        {
            return Err("Invalid object ID or role".into());
        }
        if object
            .world_matrix
            .iter()
            .flatten()
            .any(|v| !v.is_finite() || v.abs() > 1e12)
        {
            return Err(format!("Invalid transform: {}", object.id));
        }
        if let Some(b) = &object.bounds {
            if (0..3).any(|i| {
                !b.min[i].is_finite()
                    || !b.max[i].is_finite()
                    || b.min[i].abs() > 1e12
                    || b.max[i].abs() > 1e12
                    || b.min[i] > b.max[i]
            }) {
                return Err(format!("Invalid bounds: {}", object.id));
            }
        }
        let mut seen = BTreeSet::new();
        let mut current = Some(object.id.as_str());
        while let Some(id) = current {
            if !seen.insert(id) {
                return Err("Cyclic object hierarchy".into());
            }
            current = ids
                .get(id)
                .ok_or_else(|| format!("Unknown parent: {id}"))?
                .parent
                .as_deref();
        }
    }
    for id in options
        .object_id
        .iter()
        .chain(options.ground_objects.iter())
        .chain(options.contact_pairs.iter().flatten())
    {
        if !ids.contains_key(id.as_str()) {
            return Err(format!("Unknown object: {id}"));
        }
    }
    for connection in &options.connection_points {
        if connection.name.trim().is_empty() || connection.name.len() > 256 {
            return Err("Connection point names must be nonempty and at most 256 bytes".into());
        }
        if connection.object_a == connection.object_b {
            return Err(format!(
                "Connection point targets must be distinct: {}",
                connection.name
            ));
        }
        for id in [&connection.object_a, &connection.object_b] {
            if !ids.contains_key(id.as_str()) {
                return Err(format!("Unknown connection point object: {id}"));
            }
        }
        if connection
            .point_a
            .iter()
            .chain(connection.point_b.iter())
            .any(|value| !value.is_finite() || value.abs() > 1e9)
        {
            return Err(format!(
                "Invalid local connection point: {}",
                connection.name
            ));
        }
        if !connection.max_distance.is_finite() || !(0.0..=1e9).contains(&connection.max_distance) {
            return Err(format!(
                "Invalid connection point distance: {}",
                connection.name
            ));
        }
    }
    Ok(())
}

fn world_point(matrix: [[f64; 4]; 4], point: [f64; 3]) -> [f64; 3] {
    std::array::from_fn(|row| {
        matrix[row][0] * point[0]
            + matrix[row][1] * point[1]
            + matrix[row][2] * point[2]
            + matrix[row][3]
    })
}

pub fn analyze(request: Request) -> Result<Value, String> {
    let Request { scene, options } = request;
    validate(&scene, &options)?;
    let by_id: BTreeMap<_, _> = scene.objects.iter().map(|o| (o.id.as_str(), o)).collect();
    let selected: Vec<_> = by_id
        .values()
        .copied()
        .filter(|o| {
            let Some(wanted) = &options.object_id else {
                return true;
            };
            let mut current = Some(o.id.as_str());
            while let Some(id) = current {
                if id == wanted {
                    return true;
                }
                if !options.include_descendants {
                    break;
                }
                current = by_id[id].parent.as_deref();
            }
            false
        })
        .collect();
    let page: Vec<_> = selected
        .iter()
        .copied()
        .skip(options.offset)
        .take(options.limit)
        .collect();
    let mut issues = vec![];
    let mut relations = vec![];
    let triangles: u64 = selected
        .iter()
        .filter_map(|o| o.mesh.as_ref())
        .map(|m| u64::from(m.triangles))
        .sum();
    if triangles == 0 {
        issues.push(json!({"severity":"error", "code":"empty_mesh", "scope":"selection"}));
    }
    if options
        .triangle_budget
        .is_some_and(|budget| triangles > budget)
    {
        issues.push(json!({"severity":"error", "code":"triangle_budget", "actual":triangles, "maximum":options.triangle_budget}));
    }
    for object in &selected {
        if let Some(mesh) = &object.mesh {
            for (code, count, severity) in [
                ("degenerate_faces", mesh.degenerate_faces, "warning"),
                (
                    "missing_material_faces",
                    mesh.missing_material_faces,
                    "warning",
                ),
                (
                    "disconnected_components",
                    mesh.connected_components.saturating_sub(1),
                    "review",
                ),
                (
                    "non_manifold_edges",
                    mesh.non_manifold_edges,
                    if options.require_closed_mesh {
                        "error"
                    } else {
                        "review"
                    },
                ),
            ] {
                if count > 0 {
                    issues.push(
                        json!({"severity":severity,"code":code,"object":object.id,"count":count}),
                    );
                }
            }
        }
    }
    // Explicit ground targets must belong to the selection, regardless of pagination.
    for id in &options.ground_objects {
        let object = selected
            .iter()
            .find(|o| &o.id == id)
            .ok_or_else(|| format!("Ground object outside selection: {id}"))?;
        let bounds = object
            .bounds
            .as_ref()
            .ok_or_else(|| format!("Ground object has no bounds: {id}"))?;
        let gap = bounds.min[2] - options.ground_z.unwrap();
        if gap.abs() > options.tolerance {
            issues.push(json!({"severity":"warning","code":if gap > 0.0 {"above_ground_plane"} else {"below_ground_plane"},"object":id,"signed_distance":gap}));
        }
    }
    let mut contact_checks = vec![];
    for pair in &options.contact_pairs {
        if pair[0] == pair[1] {
            return Err("Contact pairs must contain distinct objects".into());
        }
        let bounds_for = |id: &str| -> Result<&Bounds, String> {
            selected
                .iter()
                .find(|o| o.id == id)
                .ok_or_else(|| format!("Contact object outside selection: {id}"))?
                .bounds
                .as_ref()
                .ok_or_else(|| format!("Contact object has no mesh bounds: {id}"))
        };
        let distance = bounds_for(&pair[0])?.distance(bounds_for(&pair[1])?);
        let separated = distance > options.tolerance;
        contact_checks.push(json!({"objects":pair,"aabb_distance_lower_bound":distance,
            "status":if separated {"gap_detected"} else {"contact_unverified"},"tolerance":options.tolerance}));
        if separated {
            issues.push(json!({"severity":"error","code":"expected_contact_gap","objects":pair,
                "minimum_gap":distance,"tolerance":options.tolerance,
                "message":"These explicitly declared touching parts have separated world bounds. Check the intended joint in the rendered views."}));
        }
    }
    // Authored local anchors are measured independently of object pagination. They only
    // verify the declared anchors, never mesh surface contact or intersection.
    let mut connection_checks = vec![];
    for connection in &options.connection_points {
        let object_a = selected
            .iter()
            .find(|object| object.id == connection.object_a)
            .ok_or_else(|| {
                format!(
                    "Connection point object outside selection: {}",
                    connection.object_a
                )
            })?;
        let object_b = selected
            .iter()
            .find(|object| object.id == connection.object_b)
            .ok_or_else(|| {
                format!(
                    "Connection point object outside selection: {}",
                    connection.object_b
                )
            })?;
        let world_point_a = world_point(object_a.world_matrix, connection.point_a);
        let world_point_b = world_point(object_b.world_matrix, connection.point_b);
        let delta_world_b_minus_a: [f64; 3] =
            std::array::from_fn(|axis| world_point_b[axis] - world_point_a[axis]);
        let distance = delta_world_b_minus_a
            .iter()
            .map(|value| value.powi(2))
            .sum::<f64>()
            .sqrt();
        let gap_detected = distance > connection.max_distance;
        let objects = [&connection.object_a, &connection.object_b];
        connection_checks.push(json!({
            "name":connection.name,
            "objects":objects,
            "world_point_a":world_point_a,
            "world_point_b":world_point_b,
            "distance":distance,
            "max_distance":connection.max_distance,
            "delta_world_b_minus_a":delta_world_b_minus_a,
            "status":if gap_detected {"gap_detected"} else {"within_tolerance"}
        }));
        if gap_detected {
            issues.push(json!({
                "severity":"error",
                "code":"connection_point_gap",
                "name":connection.name,
                "objects":objects,
                "distance":distance,
                "max_distance":connection.max_distance
            }));
        }
    }
    // Spatial relations are broad-phase candidates only and apply to this page.
    for (i, object) in page.iter().enumerate() {
        if let Some(parent) = &object.parent {
            relations.push(json!({"type":"parented_to","source":object.id,"target":parent,"evidence":"authored_hierarchy"}));
        }
        for other in page.iter().skip(i + 1) {
            if let (Some(a), Some(b)) = (&object.bounds, &other.bounds) {
                let distance = a.distance(b);
                if distance <= options.proximity {
                    let overlap = (0..3)
                        .all(|axis| a.max[axis].min(b.max[axis]) > a.min[axis].max(b.min[axis]));
                    relations.push(json!({"type":if overlap {"bounds_overlap_candidate"} else {"bounds_near_candidate"},"source":object.id,"target":other.id,"aabb_distance_lower_bound":distance,"evidence":"world_aabb_only"}));
                }
            }
        }
    }
    let mut bounds: Option<Bounds> = None;
    for object in &selected {
        if let Some(b) = &object.bounds {
            bounds = Some(match bounds {
                None => b.clone(),
                Some(a) => Bounds {
                    min: std::array::from_fn(|i| a.min[i].min(b.min[i])),
                    max: std::array::from_fn(|i| a.max[i].max(b.max[i])),
                },
            });
        }
    }
    let issue_count = issues.len();
    let relation_count = relations.len();
    let error_count = issues.iter().filter(|i| i["severity"] == "error").count();
    issues.truncate(200);
    relations.truncate(200);
    let objects: Vec<_> = page.iter().map(|o| json!({"id":o.id,"kind":o.kind,"semantic_role":o.semantic_role,"role_evidence":if o.semantic_role.is_some() {Some("authored_bas_role")} else {None},"parent":o.parent,"bounds":o.bounds,"dimensions":o.bounds.as_ref().map(Bounds::dimensions),"center":o.bounds.as_ref().map(Bounds::center),"mesh":o.mesh})).collect();
    Ok(json!({
        "schema_version":"bas-analysis/0.1", "runtime_version":env!("CARGO_PKG_VERSION"),
        "evaluation_options":options,
        "contact_checks":contact_checks,
        "connection_checks":connection_checks,
        "source":scene.source,"blender_version":scene.blender_version,"frame":scene.frame,
        "units":{"coordinates":"Blender world units","meters_per_unit":scene.meters_per_unit},
        "scene_object_count":scene.objects.len(),
        "selection":{"object_id":options.object_id,"object_count":selected.len(),"triangles":triangles,"bounds":bounds},
        "objects":objects,
        "pagination":{"offset":options.offset,"limit":options.limit,"next_offset":if options.offset + page.len() < selected.len() {Some(options.offset + page.len())} else {None}},
        "relations":{"scope":"returned page only","total":relation_count,"truncated":relation_count > 200,"items":relations},
        "quality":{"status":if error_count > 0 {"constraints_failed"} else {"review_required"},"error_count":error_count,"issue_count":issue_count,"issues_truncated":issue_count > 200,"issues":issues,
            "agent_review_required":["Review fixed front, side, rear and three-quarter views.","Do the primary forms and proportions match the brief and references?","Are overlap candidates intentional? Bounds alone cannot establish mesh intersection or contact.","Does the asset still look like a blockout?","Does the style and finish satisfy the brief?"],
            "not_measured":["triangle-level intersections and surface proximity","surface contact beyond explicitly declared connection-point anchors","geometric symmetry","reference silhouette similarity","aesthetic quality"]},
        "extraction_limitations":scene.limitations
    }))
}

#[cfg(test)]
mod tests {
    use super::*;
    fn request() -> Request {
        let object = |id: &str, x: f64, parent: Option<&str>| Object {
            id: id.into(),
            kind: "MESH".into(),
            parent: parent.map(String::from),
            semantic_role: None,
            world_matrix: [[0.0; 4]; 4],
            bounds: Some(Bounds {
                min: [x, 0.0, 1.0],
                max: [x + 1.0, 1.0, 2.0],
            }),
            mesh: Some(Mesh {
                vertices: 8,
                triangles: 12,
                connected_components: 1,
                ..Default::default()
            }),
        };
        Request {
            scene: Scene {
                schema_version: "bas-scene-ir/0.1".into(),
                source: "fixture".into(),
                blender_version: "test".into(),
                frame: 1,
                meters_per_unit: 1.0,
                limitations: vec![],
                objects: vec![
                    object("body", 0.0, None),
                    object("part", 0.5, Some("body")),
                    object("far", 4.0, None),
                ],
            },
            options: Options::default(),
        }
    }
    #[test]
    fn honest_overlap_and_no_implicit_ground_failures() {
        let value = analyze(request()).unwrap();
        assert_eq!(
            value["relations"]["items"][0]["type"],
            "bounds_overlap_candidate"
        );
        assert_eq!(value["quality"]["issue_count"], 0);
        assert_eq!(value["quality"]["status"], "review_required");
    }
    #[test]
    fn explicit_ground_and_budget_cover_unpaginated_selection() {
        let mut r = request();
        r.options.limit = 1;
        r.options.ground_z = Some(0.0);
        r.options.ground_objects = vec!["part".into()];
        r.options.triangle_budget = Some(35);
        let value = analyze(r).unwrap();
        assert_eq!(value["selection"]["triangles"], 36);
        assert_eq!(value["quality"]["error_count"], 1);
        assert_eq!(value["quality"]["issues"][1]["code"], "above_ground_plane");
        assert_eq!(value["pagination"]["next_offset"], 1);
    }
    #[test]
    fn hierarchy_selection_and_unknown_ids() {
        let mut r = request();
        r.options.object_id = Some("body".into());
        assert_eq!(analyze(r).unwrap()["selection"]["object_count"], 2);
        let mut r = request();
        r.options.object_id = Some("missing".into());
        assert!(analyze(r).is_err());
        let mut r = request();
        r.scene.objects[0].parent = Some("part".into());
        assert!(analyze(r).is_err());
        let mut r = request();
        r.scene.objects[0].parent = Some("missing".into());
        assert!(analyze(r).is_err());
    }
    #[test]
    fn rejects_invalid_bounds_duplicate_ids_and_options() {
        let mut r = request();
        r.scene.objects[0].bounds.as_mut().unwrap().min[0] = f64::NAN;
        assert!(analyze(r).is_err());
        let mut r = request();
        r.scene.objects[1].id = "body".into();
        assert!(analyze(r).is_err());
        let mut r = request();
        r.options.limit = 201;
        assert!(analyze(r).is_err());
        let mut r = request();
        r.options.ground_objects = vec!["body".into()];
        assert!(analyze(r).is_err());
        let mut r = request();
        r.scene.schema_version = "future".into();
        assert!(analyze(r).is_err());
    }
    #[test]
    fn closed_mesh_is_an_explicit_constraint() {
        let mut r = request();
        r.scene.objects[0].mesh.as_mut().unwrap().non_manifold_edges = 4;
        assert_eq!(analyze(r).unwrap()["quality"]["error_count"], 0);
        let mut r = request();
        r.scene.objects[0].mesh.as_mut().unwrap().non_manifold_edges = 4;
        r.options.require_closed_mesh = true;
        assert_eq!(analyze(r).unwrap()["quality"]["error_count"], 1);
    }
    #[test]
    fn empty_scene_is_not_a_quality_pass() {
        let mut r = request();
        r.scene.objects.clear();
        assert_eq!(
            analyze(r).unwrap()["quality"]["status"],
            "constraints_failed"
        );
    }

    #[test]
    fn explicit_contact_detects_gaps_outside_returned_page_without_proving_overlap_contact() {
        let mut r = request();
        r.options.limit = 1;
        r.options.contact_pairs = vec![
            ["body".into(), "far".into()],
            ["body".into(), "part".into()],
        ];
        let result = analyze(r).unwrap();
        assert_eq!(
            result["contact_checks"][0]["aabb_distance_lower_bound"],
            3.0
        );
        assert_eq!(result["contact_checks"][0]["status"], "gap_detected");
        assert_eq!(result["contact_checks"][1]["status"], "contact_unverified");
        assert_eq!(result["quality"]["error_count"], 1);
    }

    #[test]
    fn contact_checks_reject_invalid_targets_and_respect_tolerance() {
        let mut r = request();
        r.options.contact_pairs = vec![["body".into(), "body".into()]];
        assert!(analyze(r).is_err());
        let mut r = request();
        r.options.object_id = Some("body".into());
        r.options.contact_pairs = vec![["body".into(), "far".into()]];
        assert!(analyze(r).is_err());
        let mut r = request();
        r.scene.objects[0].bounds = None;
        r.options.contact_pairs = vec![["body".into(), "far".into()]];
        assert!(analyze(r).is_err());
        let mut r = request();
        r.options.tolerance = 3.0;
        r.options.contact_pairs = vec![["body".into(), "far".into()]];
        assert_eq!(
            analyze(r).unwrap()["contact_checks"][0]["status"],
            "contact_unverified"
        );
    }

    #[test]
    fn connection_points_transform_local_anchors_and_ignore_pagination() {
        let mut r = request();
        r.options.limit = 1;
        r.scene.objects[0].world_matrix = [
            [2.0, 0.0, 0.0, 10.0],
            [0.0, 3.0, 0.0, 20.0],
            [0.0, 0.0, 4.0, 30.0],
            [0.0, 0.0, 0.0, 1.0],
        ];
        r.scene.objects[2].world_matrix = [
            [1.0, 0.0, 0.0, 15.0],
            [0.0, 1.0, 0.0, 18.0],
            [0.0, 0.0, 1.0, 27.0],
            [0.0, 0.0, 0.0, 1.0],
        ];
        r.options.connection_points = vec![Connection {
            name: "body-to-far".into(),
            object_a: "body".into(),
            point_a: [1.0, 2.0, 3.0],
            object_b: "far".into(),
            point_b: [0.0, 0.0, 0.0],
            max_distance: 12.0,
        }];
        let value = analyze(r).unwrap();
        let check = &value["connection_checks"][0];
        assert_eq!(check["world_point_a"], json!([12.0, 26.0, 42.0]));
        assert_eq!(check["world_point_b"], json!([15.0, 18.0, 27.0]));
        assert_eq!(check["delta_world_b_minus_a"], json!([3.0, -8.0, -15.0]));
        assert_eq!(check["status"], "gap_detected");
        assert_eq!(value["connection_checks"].as_array().unwrap().len(), 1);
        assert_eq!(value["objects"].as_array().unwrap().len(), 1);
        assert_eq!(
            value["quality"]["issues"][0]["code"],
            "connection_point_gap"
        );
    }

    #[test]
    fn connection_points_respect_threshold_and_validate_inputs() {
        let mut r = request();
        r.options.connection_points = vec![Connection {
            name: "aligned".into(),
            object_a: "body".into(),
            point_a: [0.0, 0.0, 0.0],
            object_b: "far".into(),
            point_b: [0.0, 0.0, 0.0],
            max_distance: 0.0,
        }];
        assert_eq!(
            analyze(r).unwrap()["connection_checks"][0]["status"],
            "within_tolerance"
        );

        let invalid_connection = |name: &str| Connection {
            name: name.into(),
            object_a: "body".into(),
            point_a: [0.0, 0.0, 0.0],
            object_b: "far".into(),
            point_b: [0.0, 0.0, 0.0],
            max_distance: 0.0,
        };
        let mut r = request();
        r.options.connection_points = vec![invalid_connection("")];
        assert!(analyze(r).is_err());
        let mut r = request();
        let mut connection = invalid_connection("same");
        connection.object_b = "body".into();
        r.options.connection_points = vec![connection];
        assert!(analyze(r).is_err());
        let mut r = request();
        let mut connection = invalid_connection("nonfinite");
        connection.point_a[0] = f64::NAN;
        r.options.connection_points = vec![connection];
        assert!(analyze(r).is_err());
        let mut r = request();
        let mut connection = invalid_connection("distance");
        connection.max_distance = 1e9 + 1.0;
        r.options.connection_points = vec![connection];
        assert!(analyze(r).is_err());
        let mut r = request();
        r.options.object_id = Some("body".into());
        r.options.connection_points = vec![invalid_connection("outside-selection")];
        assert!(analyze(r).is_err());
    }

    #[test]
    fn connection_points_deny_malformed_fields() {
        let options = json!({
            "connection_points":[{
                "name":"joint",
                "object_a":"body",
                "point_a":[0.0, 0.0, 0.0],
                "object_b":"part",
                "point_b":[0.0, 0.0, 0.0],
                "max_distance":0.01,
                "unexpected":true
            }]
        });
        assert!(serde_json::from_value::<Options>(options).is_err());
    }
}
