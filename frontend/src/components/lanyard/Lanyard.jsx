/* eslint-disable react/no-unknown-property */
'use client';
import { useEffect, useMemo, useRef, useState } from 'react';
import { Canvas, extend, useFrame } from '@react-three/fiber';
import { useGLTF, useTexture, Environment, Lightformer, Html } from '@react-three/drei';
import { BallCollider, CuboidCollider, Physics, RigidBody, useRopeJoint, useSphericalJoint } from '@react-three/rapier';
import { MeshLineGeometry, MeshLineMaterial } from 'meshline';

import cardGLB from './card.glb';
import lanyard from './lanyard.png';

import * as THREE from 'three';
import './Lanyard.css';

extend({ MeshLineGeometry, MeshLineMaterial });

const BLANK_PIXEL =
  'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==';

// Badge gray (#D1D1D1) so HTML login face blends with the 3D card edges.
const BADGE_GRAY_PIXEL =
  'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGO4ePEiAATqAnTLCqWTAAAAAElFTkSuQmCC';

const FRONT_UV_RECT = { x: 0, y: 0, w: 0.5, h: 0.755 };
const BACK_UV_RECT = { x: 0.5, y: 0, w: 0.5, h: 0.757 };

export default function Lanyard({
  position = [0, 0, 30],
  gravity = [0, -40, 0],
  fov = 20,
  transparent = true,
  frontImage = null,
  backImage = null,
  imageFit = 'cover',
  lanyardImage = null,
  lanyardWidth = 1,
  cardContent = null,
}) {
  const [isMobile, setIsMobile] = useState(() => typeof window !== 'undefined' && window.innerWidth < 768);

  useEffect(() => {
    const handleResize = () => setIsMobile(window.innerWidth < 768);
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const resolvedFront = frontImage ?? (cardContent ? BADGE_GRAY_PIXEL : null);

  return (
    <div className="lanyard-wrapper">
      <Canvas
        camera={{ position: position, fov: fov }}
        dpr={[1, isMobile ? 1.5 : 2]}
        gl={{ alpha: transparent }}
        onCreated={({ gl }) => gl.setClearColor(new THREE.Color(0x000000), transparent ? 0 : 1)}
      >
        <ambientLight intensity={0.85} />
        <directionalLight position={[5, 7, 9]} intensity={2.4} color="#ffffff" />
        <directionalLight position={[-6, 3, 4]} intensity={0.9} color="#b8c9e8" />
        <directionalLight position={[1, -4, 6]} intensity={0.55} color="#ffd9a0" />
        <Physics gravity={gravity} timeStep={isMobile ? 1 / 30 : 1 / 60}>
          <Band
            isMobile={isMobile}
            frontImage={resolvedFront}
            backImage={backImage}
            imageFit={imageFit}
            lanyardImage={lanyardImage}
            lanyardWidth={lanyardWidth}
            cardContent={cardContent}
          />
        </Physics>
        <Environment blur={0.55}>
          <Lightformer
            intensity={2.4}
            color="white"
            position={[0, -1, 5]}
            rotation={[0, 0, Math.PI / 3]}
            scale={[100, 0.1, 1]}
          />
          <Lightformer
            intensity={3.2}
            color="white"
            position={[-1, -1, 1]}
            rotation={[0, 0, Math.PI / 3]}
            scale={[100, 0.1, 1]}
          />
          <Lightformer
            intensity={2.8}
            color="#fff4e6"
            position={[1, 1, 1]}
            rotation={[0, 0, Math.PI / 3]}
            scale={[100, 0.1, 1]}
          />
          <Lightformer
            intensity={12}
            color="white"
            position={[-10, 0, 14]}
            rotation={[0, Math.PI / 2, Math.PI / 3]}
            scale={[100, 10, 1]}
          />
          <Lightformer
            intensity={4}
            color="#e8eeff"
            position={[8, 4, -6]}
            scale={[12, 12, 1]}
          />
        </Environment>
      </Canvas>
    </div>
  );
}

function Band({
  maxSpeed = 50,
  minSpeed = 0,
  isMobile = false,
  frontImage = null,
  backImage = null,
  imageFit = 'cover',
  lanyardImage = null,
  lanyardWidth = 1,
  plainLanyard = true,
  cardContent = null,
}) {
  const band = useRef(),
    fixed = useRef(),
    j1 = useRef(),
    j2 = useRef(),
    j3 = useRef(),
    card = useRef();
  const vec = new THREE.Vector3(),
    ang = new THREE.Vector3(),
    rot = new THREE.Vector3(),
    dir = new THREE.Vector3();
  const segmentProps = { type: 'dynamic', canSleep: true, colliders: false, angularDamping: 4, linearDamping: 4 };
  const { nodes, materials } = useGLTF(cardGLB);
  // Hook must stay unconditional; pattern texture only applied when plainLanyard=false.
  const texture = useTexture(lanyardImage || lanyard);
  const frontTex = useTexture(frontImage || BLANK_PIXEL);
  const backTex = useTexture(backImage || BLANK_PIXEL);

  // Fit HTML login plane to the real card mesh face (prevents spill below badge).
  // drei Html transform uses factor 400/distanceFactor (default 40). Set distanceFactor=400
  // so 1 CSS px ≈ 1 local unit * scale, then scale = faceSize / cssSize.
  const faceFit = useMemo(() => {
    const geometry = nodes.card.geometry;
    geometry.computeBoundingBox();
    const bb = geometry.boundingBox;
    const size = new THREE.Vector3();
    const center = new THREE.Vector3();
    bb.getSize(size);
    bb.getCenter(center);

    // Design canvas is 400×630 (exported badge art). Stretch to fill mesh face.
    const cssW = 400;
    const cssH = 630;

    return {
      cssW,
      cssH,
      scale: [size.x / cssW, size.y / cssH, 1],
      position: [center.x, center.y, center.z + size.z * 0.5 + 0.02],
    };
  }, [nodes.card.geometry]);

  const cardMap = useMemo(() => {
    const baseMap = materials.base.map;
    if (!frontImage && !backImage) return baseMap;

    const baseImg = baseMap.image;
    const W = baseImg.width;
    const H = baseImg.height;
    const canvas = document.createElement('canvas');
    canvas.width = W;
    canvas.height = H;
    const ctx = canvas.getContext('2d');
    if (!ctx) return baseMap;
    ctx.drawImage(baseImg, 0, 0, W, H);

    const drawFitted = (img, rect) => {
      const rx = rect.x * W;
      const ry = rect.y * H;
      const rw = rect.w * W;
      const rh = rect.h * H;
      const pick = imageFit === 'contain' ? Math.min : Math.max;
      const scale = pick(rw / img.width, rh / img.height);
      const dw = img.width * scale;
      const dh = img.height * scale;
      const dx = rx + (rw - dw) / 2;
      const dy = ry + (rh - dh) / 2;
      ctx.save();
      ctx.beginPath();
      ctx.rect(rx, ry, rw, rh);
      ctx.clip();
      ctx.drawImage(img, dx, dy, dw, dh);
      ctx.restore();
    };

    if (frontImage && frontTex.image) drawFitted(frontTex.image, FRONT_UV_RECT);
    if (backImage && backTex.image) drawFitted(backTex.image, BACK_UV_RECT);

    const composite = new THREE.CanvasTexture(canvas);
    composite.colorSpace = THREE.SRGBColorSpace;
    composite.flipY = baseMap.flipY;
    composite.anisotropy = 16;
    composite.needsUpdate = true;
    return composite;
  }, [frontImage, backImage, imageFit, frontTex, backTex, materials.base.map]);

  const [curve] = useState(
    () =>
      new THREE.CatmullRomCurve3([new THREE.Vector3(), new THREE.Vector3(), new THREE.Vector3(), new THREE.Vector3()])
  );
  const [dragged, drag] = useState(false);
  const [hovered, hover] = useState(false);

  useRopeJoint(fixed, j1, [[0, 0, 0], [0, 0, 0], 1]);
  useRopeJoint(j1, j2, [[0, 0, 0], [0, 0, 0], 1]);
  useRopeJoint(j2, j3, [[0, 0, 0], [0, 0, 0], 1]);
  // Attach at clip so rope and metal read as one piece through the slot.
  useSphericalJoint(j3, card, [
    [0, 0, 0],
    [0, 1.42, 0]
  ]);

  useEffect(() => {
    if (hovered) {
      document.body.style.cursor = dragged ? 'grabbing' : 'grab';
      return () => void (document.body.style.cursor = 'auto');
    }
  }, [hovered, dragged]);

  useFrame((state, delta) => {
    if (dragged) {
      vec.set(state.pointer.x, state.pointer.y, 0.5).unproject(state.camera);
      dir.copy(vec).sub(state.camera.position).normalize();
      vec.add(dir.multiplyScalar(state.camera.position.length()));
      [card, j1, j2, j3, fixed].forEach(ref => ref.current?.wakeUp());
      card.current?.setNextKinematicTranslation({ x: vec.x - dragged.x, y: vec.y - dragged.y, z: vec.z - dragged.z });
    }
    if (fixed.current) {
      [j1, j2].forEach(ref => {
        if (!ref.current.lerped) ref.current.lerped = new THREE.Vector3().copy(ref.current.translation());
        const clampedDistance = Math.max(0.1, Math.min(1, ref.current.lerped.distanceTo(ref.current.translation())));
        ref.current.lerped.lerp(
          ref.current.translation(),
          delta * (minSpeed + clampedDistance * (maxSpeed - minSpeed))
        );
      });
      curve.points[0].copy(j3.current.translation());
      curve.points[1].copy(j2.current.lerped);
      curve.points[2].copy(j1.current.lerped);
      curve.points[3].copy(fixed.current.translation());
      band.current.geometry.setPoints(curve.getPoints(isMobile ? 16 : 32));
      ang.copy(card.current.angvel());
      rot.copy(card.current.rotation());
      card.current.setAngvel({ x: ang.x, y: ang.y - rot.y * 0.25, z: ang.z });
    }
  });

  curve.curveType = 'chordal';
  if (!plainLanyard) {
    texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
  }

  const beginDrag = (e) => {
    e.stopPropagation();
    e.target.setPointerCapture(e.pointerId);
    drag(new THREE.Vector3().copy(e.point).sub(vec.copy(card.current.translation())));
  };

  const endDrag = (e) => {
    e.target.releasePointerCapture(e.pointerId);
    drag(false);
  };

  return (
    <>
      <group position={[0, 4.15, 0]}>
        <RigidBody ref={fixed} {...segmentProps} type="fixed" />
        <RigidBody position={[0.5, 0, 0]} ref={j1} {...segmentProps}>
          <BallCollider args={[0.1]} />
        </RigidBody>
        <RigidBody position={[1, 0, 0]} ref={j2} {...segmentProps}>
          <BallCollider args={[0.1]} />
        </RigidBody>
        <RigidBody position={[1.5, 0, 0]} ref={j3} {...segmentProps}>
          <BallCollider args={[0.1]} />
        </RigidBody>
        <RigidBody
          position={[2, 0, 0]}
          rotation={[0.05, 0.14, 0.02]}
          ref={card}
          {...segmentProps}
          type={dragged ? 'kinematicPosition' : 'dynamic'}
        >
          <CuboidCollider args={[0.8, 1.125, 0.01]} />
          <group scale={2.33} position={[0, -1.2, -0.05]}>
            <mesh
              geometry={nodes.card.geometry}
              onPointerOver={() => hover(true)}
              onPointerOut={() => hover(false)}
              onPointerUp={endDrag}
              onPointerDown={beginDrag}
            >
              <meshPhysicalMaterial
                map={cardMap}
                map-anisotropy={16}
                color={cardContent ? '#d4d4d4' : '#ffffff'}
                clearcoat={isMobile ? 0 : cardContent ? 0.42 : 1}
                clearcoatRoughness={cardContent ? 0.38 : 0.15}
                roughness={cardContent ? 0.4 : 0.85}
                metalness={cardContent ? 0.08 : 0.8}
                envMapIntensity={cardContent ? 0.85 : 1}
                sheen={cardContent ? 0.35 : 0}
                sheenRoughness={0.55}
                sheenColor="#ffffff"
              />
            </mesh>
            {cardContent && (
              <Html
                transform
                occlude={false}
                distanceFactor={400}
                position={faceFit.position}
                scale={faceFit.scale}
                // Inner transform wrapper defaults to pointerEvents="auto" and
                // blocks canvas raycasts; only form controls re-enable hits.
                pointerEvents="none"
                style={{
                  width: `${faceFit.cssW}px`,
                  height: `${faceFit.cssH}px`,
                  overflow: 'visible',
                }}
              >
                {cardContent}
              </Html>
            )}
            <mesh
              geometry={nodes.clip.geometry}
              position={[0, -0.02, 0.12]}
              renderOrder={10}
              onPointerOver={() => hover(true)}
              onPointerOut={() => hover(false)}
              onPointerUp={endDrag}
              onPointerDown={beginDrag}
            >
              <meshPhysicalMaterial
                color="#0a0a0a"
                metalness={1}
                roughness={0.18}
                clearcoat={0.55}
                clearcoatRoughness={0.15}
                envMapIntensity={1.6}
                depthTest={false}
                depthWrite={false}
              />
            </mesh>
            <mesh
              geometry={nodes.clamp.geometry}
              position={[0, -0.02, 0.12]}
              renderOrder={10}
              onPointerOver={() => hover(true)}
              onPointerOut={() => hover(false)}
              onPointerUp={endDrag}
              onPointerDown={beginDrag}
            >
              <meshPhysicalMaterial
                color="#111111"
                metalness={1}
                roughness={0.28}
                clearcoat={0.4}
                clearcoatRoughness={0.25}
                envMapIntensity={1.35}
                depthTest={false}
                depthWrite={false}
              />
            </mesh>
          </group>
        </RigidBody>
      </group>
      <mesh ref={band}>
        <meshLineGeometry />
        {plainLanyard ? (
          <meshLineMaterial
            color="#141414"
            depthTest={false}
            resolution={isMobile ? [1000, 2000] : [1000, 1000]}
            lineWidth={lanyardWidth}
          />
        ) : (
          <meshLineMaterial
            color="white"
            depthTest={false}
            resolution={isMobile ? [1000, 2000] : [1000, 1000]}
            useMap
            map={texture}
            repeat={[-4, 1]}
            lineWidth={lanyardWidth}
          />
        )}
      </mesh>
    </>
  );
}
