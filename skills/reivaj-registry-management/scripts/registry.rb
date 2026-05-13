#!/usr/bin/env ruby
# frozen_string_literal: true

require 'yaml'
require 'set'
require 'optparse'

ROOT = File.expand_path('../../..', __dir__)
REGISTRY_DIR = File.join(ROOT, 'registry')

def catalog_paths
  Dir[File.join(REGISTRY_DIR, '**/*.yaml')].reject do |path|
    File.basename(path).match?(/\A(schema|taxonomy)\.yaml\z/)
  end.sort
end

def load_yaml(path)
  YAML.safe_load(File.read(path), permitted_classes: [Symbol], aliases: false) || {}
rescue Psych::Exception => e
  raise "#{path}: invalid YAML: #{e.message}"
end

def load_catalogs
  catalog_paths.map do |path|
    data = load_yaml(path)
    source = data.fetch('source', {})
    items = data.fetch('items', [])
    { path: path, source: source, items: items }
  end
end

def item_key(catalog, item)
  "#{catalog[:source]['id'] || File.basename(catalog[:path], '.yaml')}:#{item['id']}"
end

def item_text(catalog, item)
  ([item['id'], item['name'], item['summary'], item['source'], catalog[:source]['label']] + Array(item['tags'])).compact.join(' ').downcase
end

def tokenize(text)
  text.downcase.scan(/[a-z0-9][a-z0-9_-]{2,}/).to_set
end

def validate
  errors = []

  load_catalogs.each do |catalog|
    source = catalog[:source]
    path = catalog[:path]
    source_type = source['source_type']
    seen_in_catalog = Set.new

    %w[id label source_type].each do |field|
      errors << "#{path}: missing source.#{field}" if source[field].to_s.strip.empty?
    end

    unless %w[external internal].include?(source_type)
      errors << "#{path}: source.source_type must be external or internal"
    end

    unless catalog[:items].is_a?(Array)
      errors << "#{path}: items must be an array"
      next
    end

    catalog[:items].each_with_index do |item, index|
      location = "#{path}:items[#{index}]"
      %w[id name source summary tags maturity].each do |field|
        errors << "#{location}: missing #{field}" if item[field].nil? || item[field].to_s.strip.empty?
      end

      if item['tags'] && !item['tags'].is_a?(Array)
        errors << "#{location}: tags must be an array"
      end

      if item['id'] && seen_in_catalog.include?(item['id'])
        errors << "#{location}: duplicate id inside catalog: #{item['id']}"
      end
      seen_in_catalog << item['id'] if item['id']

      source_value = item['source'].to_s
      if source_type == 'external' && !source_value.match?(%r{\Ahttps?://})
        errors << "#{location}: external source must be a web URL"
      end
      if source_type == 'internal' && source_value.match?(%r{\Ahttps?://})
        errors << "#{location}: internal source must be repository-relative"
      end
    end
  end

  if errors.empty?
    puts 'registry valid'
    return true
  end

  warn errors.join("\n")
  false
end

def search(argv)
  options = { tags: [] }
  parser = OptionParser.new do |opts|
    opts.on('--tag TAG', 'Require tag. Can be used multiple times.') { |tag| options[:tags] << tag }
    opts.on('--limit N', Integer, 'Limit results.') { |n| options[:limit] = n }
  end
  parser.parse!(argv)
  query = argv.join(' ').downcase.strip
  query_tokens = tokenize(query).to_a

  results = []
  load_catalogs.each do |catalog|
    catalog[:items].each do |item|
      tags = Array(item['tags']) + [item['maturity'], "source_type:#{catalog[:source]['source_type']}"].compact
      next unless options[:tags].all? { |tag| tags.include?(tag) }

      text = item_text(catalog, item)
      next unless query.empty? || query_tokens.any? { |token| text.include?(token) }

      score = 0
      query_tokens.each do |token|
        score += 3 if item['id'].to_s.downcase.include?(token) || item['name'].to_s.downcase.include?(token)
        score += 2 if item['summary'].to_s.downcase.include?(token)
        score += 1 if tags.any? { |tag| tag.downcase.include?(token) }
      end
      score += options[:tags].length
      results << [score, catalog, item, tags]
    end
  end

  results.sort_by! { |score, _catalog, item, _tags| [-score, item['id'].to_s] }
  results = results.first(options[:limit]) if options[:limit]

  results.each do |_score, catalog, item, tags|
    puts "#{item_key(catalog, item)}"
    puts "  source: #{item['source']}"
    puts "  summary: #{item['summary']}"
    puts "  tags: #{tags.compact.join(', ')}"
  end
end

def overlap(argv)
  threshold = 0.35
  include_components = false
  OptionParser.new do |opts|
    opts.on('--threshold N', Float, 'Jaccard threshold, default 0.35') { |n| threshold = n }
    opts.on('--include-components', 'Include component inventory records.') { include_components = true }
  end.parse!(argv)

  records = load_catalogs.flat_map do |catalog|
    next [] if !include_components && catalog[:source]['id'] == 'adk-sample-components'

    catalog[:items].map do |item|
      tags = Array(item['tags']).to_set
      words = tokenize([item['name'], item['summary'], item['metadata']&.values].flatten.compact.join(' '))
      { catalog: catalog, item: item, tokens: tags + words }
    end
  end

  pairs = []
  records.combination(2) do |left, right|
    union = left[:tokens] | right[:tokens]
    next if union.empty?
    score = ((left[:tokens] & right[:tokens]).length.to_f / union.length).round(3)
    pairs << [score, left, right] if score >= threshold
  end

  pairs.sort_by { |score, _left, _right| -score }.each do |score, left, right|
    puts "#{score} #{item_key(left[:catalog], left[:item])} <=> #{item_key(right[:catalog], right[:item])}"
  end
end

def improvements
  issues = []

  load_catalogs.each do |catalog|
    source_type = catalog[:source]['source_type']
    seen_in_catalog = Hash.new { |hash, key| hash[key] = [] }

    catalog[:items].each do |item|
      key = item_key(catalog, item)
      tags = Array(item['tags'])
      seen_in_catalog[item['id']] << key

      issues << "#{key}: summary is short" if item['summary'].to_s.length < 50
      issues << "#{key}: missing tags" if tags.empty?
      issues << "#{key}: missing entity:* tag" unless tags.any? { |tag| tag.start_with?('entity:') }
      issues << "#{key}: missing capability/pattern/integration/domain tag" unless tags.any? { |tag| tag.match?(/\A(capability|pattern|integration|domain):/) }
      issues << "#{key}: external item source is not URL" if source_type == 'external' && !item['source'].to_s.match?(%r{\Ahttps?://})
      issues << "#{key}: internal item source is URL" if source_type == 'internal' && item['source'].to_s.match?(%r{\Ahttps?://})
    end

    seen_in_catalog.each do |id, keys|
      issues << "duplicate id inside catalog #{id}: #{keys.join(', ')}" if keys.length > 1
    end
  end

  puts issues.empty? ? 'no obvious improvements found' : issues.join("\n")
end

def add_item(argv)
  catalog_path, item_path = argv
  abort 'usage: add CATALOG.yaml ITEM.yaml' unless catalog_path && item_path

  catalog = load_yaml(File.expand_path(catalog_path, ROOT))
  item = load_yaml(File.expand_path(item_path, ROOT))
  abort 'item YAML must be a mapping' unless item.is_a?(Hash)

  catalog['items'] ||= []
  if catalog['items'].any? { |existing| existing['id'] == item['id'] }
    abort "item id already exists in catalog: #{item['id']}"
  end

  catalog['items'] << item
  File.write(File.expand_path(catalog_path, ROOT), YAML.dump(catalog, line_width: -1).sub(/^---\n/, ''))
  abort 'registry invalid after add' unless validate
end

def serve(argv)
  port = argv.first || '8000'
  Dir.chdir(ROOT) do
    exec('python3', '-m', 'http.server', port)
  end
end

command = ARGV.shift
case command
when 'validate' then exit(validate ? 0 : 1)
when 'search' then search(ARGV)
when 'overlap' then overlap(ARGV)
when 'improvements' then improvements
when 'add' then add_item(ARGV)
when 'serve' then serve(ARGV)
else
  warn <<~USAGE
    usage: registry.rb COMMAND [ARGS]

    commands:
      validate
      search QUERY [--tag TAG] [--limit N]
      overlap [--threshold N]
      improvements
      add CATALOG.yaml ITEM.yaml
      serve [PORT]
  USAGE
  exit 2
end
