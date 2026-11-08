// Validator for the documented JSON Schema subset used by this package.
// Not a general-purpose replacement for a full Draft 2020-12 implementation.
export function validate(value,schema,root=schema,p='$'){
 const errors=[];const fail=s=>errors.push(p+': '+s);
 if(schema.$ref){const target=schema.$ref.split('/').slice(1).reduce((v,k)=>v[k],root);return validate(value,target,root,p);}
 if(schema.const!==undefined&&JSON.stringify(value)!==JSON.stringify(schema.const))fail('const');
 if(schema.enum&&!schema.enum.some(x=>JSON.stringify(x)===JSON.stringify(value)))fail('enum');
 const type=value===null?'null':Array.isArray(value)?'array':typeof value;
 if(schema.type&&!([schema.type].flat()).includes(type))fail('type '+schema.type);
 if(schema.oneOf&&schema.oneOf.filter(s=>!validate(value,s,root,p).length).length!==1)fail('oneOf');
 if(schema.allOf)for(const s of schema.allOf)errors.push(...validate(value,s,root,p));
 if(schema.not&&!validate(value,schema.not,root,p).length)fail('not');
 if(schema.if){const chosen=validate(value,schema.if,root,p).length?schema.else:schema.then;if(chosen)errors.push(...validate(value,chosen,root,p));}
 if(type==='object'){
  for(const k of schema.required||[])if(!(k in value))fail('missing '+k);
  for(const [k,v]of Object.entries(value)){
   if(schema.properties?.[k])errors.push(...validate(v,schema.properties[k],root,p+'.'+k));
   else if(schema.additionalProperties===false)fail('extra '+k);
   else if(typeof schema.additionalProperties==='object')errors.push(...validate(v,schema.additionalProperties,root,p+'.'+k));
  }
 }
 if(type==='array'){
  if(schema.minItems&&value.length<schema.minItems)fail('minItems');
  if(schema.uniqueItems&&new Set(value.map(x=>JSON.stringify(x))).size!==value.length)fail('uniqueItems');
  if(schema.items)value.forEach((v,i)=>errors.push(...validate(v,schema.items,root,p+'['+i+']')));
 }
 if(type==='string'){
  if(schema.minLength&&value.length<schema.minLength)fail('minLength');
  if(schema.pattern&&!new RegExp(schema.pattern).test(value))fail('pattern');
  if(schema.format==='date'&&(!/^\d{4}-\d{2}-\d{2}$/.test(value)||Number.isNaN(Date.parse(value))))fail('date');
  if(schema.format==='date-time'&&Number.isNaN(Date.parse(value)))fail('date-time');
  if(schema.format==='uri'){try{new URL(value);}catch{fail('uri');}}
 }
 return errors;
}
